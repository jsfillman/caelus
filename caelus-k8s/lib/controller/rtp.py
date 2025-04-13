#!/usr/bin/env python3
"""
RTP receiver module for Caelus K8s controller.
"""

import logging
import time
import numpy as np
import socket
import struct
import threading
import queue
from pyo import *

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RTPReceiver:
    """RTP audio receiver."""
    
    def __init__(self, sr=44100, buffer_size=1024, nchnls=1):
        """Initialize RTP receiver.
        
        Args:
            sr (int): Sample rate
            buffer_size (int): Buffer size for audio processing
            nchnls (int): Number of audio channels
        """
        self.sr = sr
        self.buffer_size = buffer_size
        self.nchnls = nchnls
        
        self.socket = None
        self.receive_thread = None
        self.running = False
        
        # Audio processing
        self.server = None
        self.mixer = None
        
        # RTP jitter buffers (one per worker/SSRC)
        self.jitter_buffers = {}  # ssrc -> queue
        self.jitter_buffer_size = 3  # Number of packets to buffer
        
        # Last sequence numbers
        self.last_sequence = {}  # ssrc -> last sequence number
        
        # Active tone generators (for playback)
        self.tone_generators = {}  # ssrc -> pyo object
        
        logger.info("RTP receiver initialized")
    
    def _parse_rtp_packet(self, packet):
        """Parse an RTP packet.
        
        Args:
            packet (bytes): RTP packet data
            
        Returns:
            tuple: (ssrc, sequence_number, timestamp, payload)
        """
        if len(packet) < 12:
            logger.error("RTP packet too short")
            return None
        
        # Parse header
        header = struct.unpack("!BBHII", packet[:12])
        
        # Extract fields
        byte1 = header[0]
        byte2 = header[1]
        sequence_number = header[2]
        timestamp = header[3]
        ssrc = header[4]
        
        # Extract version, padding, extension, cc, marker, payload_type
        version = (byte1 >> 6) & 0x3
        padding = (byte1 >> 5) & 0x1
        extension = (byte1 >> 4) & 0x1
        cc = byte1 & 0xF
        marker = (byte2 >> 7) & 0x1
        payload_type = byte2 & 0x7F
        
        # Skip CSRC identifiers if any
        header_size = 12 + (4 * cc)
        
        # Handle extension header if present
        if extension == 1 and len(packet) >= header_size + 4:
            ext_header = struct.unpack("!HH", packet[header_size:header_size+4])
            ext_profile = ext_header[0]
            ext_length = ext_header[1]
            header_size += 4 + (4 * ext_length)
        
        # Extract payload
        payload = packet[header_size:]
        
        return (ssrc, sequence_number, timestamp, payload)
    
    def _extract_midi_note(self, data):
        """Extract MIDI note from audio data.
        
        This is a simple heuristic function that tries to guess the MIDI note
        from the frequency content of the audio. For the MVP, it's simplified.
        
        Args:
            data (numpy.ndarray): Audio data
            
        Returns:
            int: Approximate MIDI note number
        """
        # Simple zero-crossing method for frequency estimation
        if len(data) < 100:
            return 60  # Default to middle C
            
        # Find zero crossings
        zero_crossings = np.where(np.diff(np.signbit(data)))[0]
        if len(zero_crossings) < 2:
            return 60
            
        # Calculate average period
        periods = np.diff(zero_crossings)
        avg_period = np.mean(periods) * 2  # Multiply by 2 for full period
        
        # Calculate frequency
        frequency = self.sr / avg_period if avg_period > 0 else 440
        
        # Convert to MIDI note
        if frequency <= 0:
            return 60
            
        midi_note = int(69 + 12 * np.log2(frequency / 440.0))
        
        # Clamp to valid MIDI range
        return max(0, min(127, midi_note))
    
    def _process_audio_packet(self, ssrc, sequence_number, timestamp, payload):
        """Process an audio packet.
        
        Args:
            ssrc (int): Synchronization source
            sequence_number (int): RTP sequence number
            timestamp (int): RTP timestamp
            payload (bytes): Audio payload
        """
        try:
            # Convert PCM bytes to numpy array
            audio_data = np.frombuffer(payload, dtype=np.int16).astype(np.float32) / 32767.0
            
            # Check for sequence number discontinuity (packet loss)
            if ssrc in self.last_sequence:
                expected_seq = (self.last_sequence[ssrc] + 1) & 0xFFFF
                if sequence_number != expected_seq:
                    gap = (sequence_number - expected_seq) & 0xFFFF
                    if gap < 1000:  # Sanity check
                        logger.warning(f"Packet loss detected for SSRC {ssrc}: {gap} packets")
            
            # Update last sequence number
            self.last_sequence[ssrc] = sequence_number
            
            worker_id = ssrc  # For the MVP, we'll use SSRC as worker ID
            
            # Get or create jitter buffer for this SSRC
            if ssrc not in self.jitter_buffers:
                self.jitter_buffers[ssrc] = queue.Queue(maxsize=self.jitter_buffer_size * 2)
            
            # Add to jitter buffer (if not full)
            try:
                self.jitter_buffers[ssrc].put_nowait((timestamp, audio_data))
                logger.debug(f"Added packet to jitter buffer for worker {worker_id}")
            except queue.Full:
                logger.warning(f"Jitter buffer full for worker {worker_id}, dropping packet")
            
            # Play audio if server is running
            if self.server is not None and self.server.getIsStarted():
                if ssrc not in self.tone_generators:
                    # Try to estimate the note frequency
                    midi_note = self._extract_midi_note(audio_data)
                    frequency = 440.0 * (2.0 ** ((midi_note - 69) / 12.0))
                    
                    # Create a sine oscillator for playback
                    amp = np.max(np.abs(audio_data)) if len(audio_data) > 0 else 0.3
                    self.tone_generators[ssrc] = Sine(freq=frequency, mul=amp).out()
                    logger.info(f"Playing audio from worker {worker_id} (note: {midi_note}, freq: {frequency:.1f} Hz)")
        except Exception as e:
            logger.error(f"Error processing audio packet: {e}")
    
    def _stop_tone(self, ssrc):
        """Stop a tone generator.
        
        Args:
            ssrc (int): Synchronization source
        """
        if ssrc in self.tone_generators:
            try:
                # Apply a short fade out
                self.tone_generators[ssrc].mul = 0
                # Remove from active tones
                del self.tone_generators[ssrc]
                logger.debug(f"Stopped tone for SSRC {ssrc}")
            except Exception as e:
                logger.error(f"Error stopping tone: {e}")
    
    def _receive_thread_func(self):
        """Thread function for receiving RTP packets."""
        logger.info(f"RTP receive thread started on port {self.port}")
        
        while self.running:
            try:
                # Receive packet (with timeout)
                self.socket.settimeout(0.5)
                packet, addr = self.socket.recvfrom(4096)
                
                # Parse RTP packet
                rtp_data = self._parse_rtp_packet(packet)
                if rtp_data:
                    ssrc, sequence, timestamp, payload = rtp_data
                    self._process_audio_packet(ssrc, sequence, timestamp, payload)
                
            except socket.timeout:
                # This is expected - allows the thread to check self.running
                pass
            except Exception as e:
                logger.error(f"Error receiving RTP packet: {e}")
        
        logger.info("RTP receive thread stopped")
    
    def setup(self, port=5000):
        """Set up RTP receiver on a specific port.
        
        Args:
            port (int): Port to listen on for RTP
        """
        try:
            self.port = port
            
            # Create UDP socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.bind(("0.0.0.0", port))
            
            # Start receive thread
            self.running = True
            self.receive_thread = threading.Thread(target=self._receive_thread_func)
            self.receive_thread.daemon = True
            self.receive_thread.start()
            
            # Initialize Pyo server for audio output
            self.server = Server(sr=self.sr, nchnls=self.nchnls, 
                              buffersize=self.buffer_size, duplex=0)
            self.server.setVerbosity(1)
            self.server.setOutputDevice(0)  # Use default output device
            self.server.boot()
            self.server.start()
            
            # Create a master mixer
            self.mixer = Mixer(outs=self.nchnls, chnls=16)  # Support up to 16 input channels
            self.mixer.out()
            
            logger.info(f"RTP receiver set up on port {port}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting up RTP receiver: {e}")
            self.stop()
            return False
    
    def stop(self):
        """Stop the RTP receiver."""
        # Stop all tone generators
        for ssrc in list(self.tone_generators.keys()):
            self._stop_tone(ssrc)
        
        # Stop receive thread
        self.running = False
        if self.receive_thread:
            self.receive_thread.join(timeout=2.0)
            self.receive_thread = None
        
        # Close socket
        if self.socket:
            self.socket.close()
            self.socket = None
        
        # Shut down audio
        if self.server:
            self.server.stop()
            self.server.shutdown()
            self.server = None
            
        logger.info("RTP receiver stopped")
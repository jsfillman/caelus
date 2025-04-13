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
    
    def __init__(self, sr=44100, buffer_size=1024, nchnls=2):
        """Initialize RTP receiver.
        
        Args:
            sr (int): Sample rate
            buffer_size (int): Buffer size for audio processing
            nchnls (int): Number of audio channels (changed to 2 for better compatibility)
        """
        self.sr = sr
        self.buffer_size = buffer_size
        self.nchnls = nchnls
        
        # Socket dict - multiple sockets for different ports
        self.sockets = {}  # port -> socket
        self.receive_threads = {}  # port -> thread
        self.running = False
        # Base port
        self.base_port = None
        
        # Audio processing
        self.server = None
        self.mixer = None
        
        # RTP jitter buffers (one per worker/SSRC)
        self.jitter_buffers = {}  # ssrc -> queue
        self.jitter_buffer_size = 100  # Much larger buffer (increased from 20)
        
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
    
    def _process_audio_packet(self, ssrc, sequence_number, timestamp, payload, port=None):
        """Process an audio packet.
        
        Args:
            ssrc (int): Synchronization source
            sequence_number (int): RTP sequence number
            timestamp (int): RTP timestamp
            payload (bytes): Audio payload
            port (int): Port the packet was received on (used for MIDI note estimation)
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
            
            # Add to jitter buffer, managing it better
            buffer_q = self.jitter_buffers[ssrc]
            
            if buffer_q.full():
                # If buffer is full, drop oldest packet instead of newest
                try:
                    # Remove oldest item
                    buffer_q.get_nowait()
                    # Then add new one
                    buffer_q.put_nowait((timestamp, audio_data))
                    # Use debug level to avoid log spam
                    logger.debug(f"Jitter buffer full for worker {worker_id}, replaced oldest packet")
                except Exception as e:
                    logger.debug(f"Error managing jitter buffer: {e}")
            else:
                # If there's room, add normally
                buffer_q.put_nowait((timestamp, audio_data))
                logger.debug(f"Added packet to jitter buffer for worker {worker_id}")
            
            # Play audio if server is running
            if self.server is not None and self.server.getIsStarted():
                # For MIDI input, use a combination of port offset and SSRC to create a unique ID
                # This allows different notes to have different IDs
                note_offset = 0
                if port is not None and self.base_port is not None:
                    note_offset = port - self.base_port
                
                # Create a unique tone ID
                tone_id = f"{ssrc}_{note_offset}_{timestamp % 1000}"
                
                if tone_id not in self.tone_generators:
                    # Try to extract the actual note being played
                    midi_note = None
                    
                    # If port information is available, use it to estimate MIDI note
                    if port is not None and self.base_port is not None:
                        # Calculate MIDI note from port offset (e.g., port 5001 = note 60+1)
                        port_offset = port - self.base_port
                        if 0 <= port_offset < 10:  # Sanity check
                            # Map port offset 0-9 to notes
                            note_base = 60  # Middle C
                            midi_note = note_base + port_offset
                    
                    # If no MIDI note from port, try to estimate from audio
                    if midi_note is None:
                        midi_note = self._extract_midi_note(audio_data)
                    
                    # Generate frequency from the MIDI note
                    frequency = 440.0 * (2.0 ** ((midi_note - 69) / 12.0))
                    
                    # Limit frequency to a reasonable range (between C2 and C6)
                    if frequency < 65.4:  # C2
                        frequency = 261.63  # Default to middle C
                    elif frequency > 1046.5:  # C6
                        frequency = 523.25  # C5
                    
                    # Create a sine oscillator for playback
                    amp = float(np.max(np.abs(audio_data)) if len(audio_data) > 0 else 0.3)
                    
                    # Create the sine oscillator and play it
                    self.tone_generators[tone_id] = Sine(freq=float(frequency), mul=amp).out()
                    
                    logger.info(f"Playing audio from worker {worker_id} on port {port} (note: {midi_note}, freq: {frequency:.1f} Hz, id: {tone_id})")
                
                # Handle release for previous tone if needed
                if len(self.tone_generators) > 10:  # Set a limit to avoid too many simultaneous tones
                    # Stop the oldest tone (first in the dictionary)
                    old_ids = list(self.tone_generators.keys())
                    if old_ids and old_ids[0] != tone_id:
                        self._stop_tone(old_ids[0])
        except Exception as e:
            logger.error(f"Error processing audio packet: {e}")
    
    def _stop_tone(self, tone_id):
        """Stop a tone generator.
        
        Args:
            tone_id (int): ID of the tone to stop
        """
        if tone_id in self.tone_generators:
            try:
                # Apply a smoother fade out
                # Create a fade out over 100ms
                fade = Fader(fadein=0.0, fadeout=0.1, dur=0.1, mul=self.tone_generators[tone_id].mul)
                self.tone_generators[tone_id].mul = fade
                
                # Schedule removal after the fade completes
                def _remove_after_fade():
                    time.sleep(0.15)  # Wait a bit longer than the fade
                    if tone_id in self.tone_generators:
                        # First stop the generators
                        try:
                            self.tone_generators[tone_id].stop()
                        except:
                            pass
                        # Then remove from the dictionary
                        del self.tone_generators[tone_id]
                
                # Start the removal thread
                t = threading.Thread(target=_remove_after_fade)
                t.daemon = True
                t.start()
                logger.debug(f"Stopped tone ID {tone_id}")
            except Exception as e:
                logger.error(f"Error stopping tone: {e}")
    
    def _receive_thread_func(self, port):
        """Thread function for receiving RTP packets.
        
        Args:
            port (int): Port to listen on
        """
        logger.info(f"RTP receive thread started on port {port}")
        
        socket = self.sockets.get(port)
        if socket is None:
            logger.error(f"No socket for port {port}")
            return
        
        while self.running:
            try:
                # Receive packet (with timeout)
                socket.settimeout(0.5)
                packet, addr = socket.recvfrom(4096)
                
                # Parse RTP packet
                rtp_data = self._parse_rtp_packet(packet)
                if rtp_data:
                    ssrc, sequence, timestamp, payload = rtp_data
                    self._process_audio_packet(ssrc, sequence, timestamp, payload, port)
                
            except (TimeoutError, OSError) as e:
                # This is expected - allows the thread to check self.running
                # In Python 3.12, socket.timeout is a subclass of OSError
                pass
            except Exception as e:
                logger.error(f"Error receiving RTP packet on port {port}: {e}")
        
        logger.info(f"RTP receive thread stopped for port {port}")
    
    def setup(self, port=5000, offline=False):
        """Set up RTP receiver on a specific port.
        
        Args:
            port (int): Base port to listen on for RTP
            offline (bool): If True, use offline audio mode
        """
        try:
            self.base_port = port
            
            # Create multiple sockets for different ports
            for port_offset in range(10):  # Support 10 different MIDI notes
                current_port = port + port_offset
                
                # Create socket for this port
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                try:
                    sock.bind(("0.0.0.0", current_port))
                    self.sockets[current_port] = sock
                    logger.info(f"Bound socket to port {current_port}")
                except Exception as e:
                    logger.error(f"Failed to bind socket to port {current_port}: {e}")
                    sock.close()
                    continue  # Skip this port
            
            if not self.sockets:
                logger.error("Failed to bind any sockets")
                return False
            
            # Start the audio server
            try:
                # Try to list available audio devices to help with debugging
                try:
                    logger.info("Available audio devices:")
                    pa_list_devices()
                except Exception as e:
                    logger.warning(f"Could not list audio devices: {e}")
                
                # Initialize Pyo server for audio output
                if offline:
                    # Use offline mode when requested
                    logger.info("Setting up server in offline mode (no audio output)")
                    self.server = Server(sr=44100, nchnls=2, buffersize=512, audio='offline')
                    self.server.boot()
                    logger.info(f"RTP receiver set up on ports {port}-{port+9} (offline mode)")
                else:
                    # Try with real audio output
                    self.server = Server(sr=self.sr, nchnls=self.nchnls, 
                                      buffersize=self.buffer_size, duplex=0)
                    
                    # Don't specify any specific output device, use default
                    self.server.setVerbosity(1)
                    self.server.boot()
                    self.server.start()
                    
                    # Create a master mixer
                    self.mixer = Mixer(outs=self.nchnls, chnls=16)  # Support up to 16 input channels
                    self.mixer.out()
                    
                    logger.info(f"RTP receiver set up on ports {port}-{port+9}")
            except Exception as e:
                logger.error(f"Error setting up audio server, trying fallback settings: {e}")
                
                # Try fallback with minimal settings
                self.server = Server(sr=44100, nchnls=2, buffersize=512, audio='offline')
                self.server.boot()
                
                # Just generate sine wave and log a message that audio is playing
                logger.info("Using offline audio mode - no audio output")
            
            # Start receive threads for all sockets
            self.running = True
            for port, sock in self.sockets.items():
                thread = threading.Thread(target=self._receive_thread_func, args=(port,))
                thread.daemon = True
                thread.start()
                self.receive_threads[port] = thread
            
            return True
                
        except Exception as e:
            logger.error(f"Error setting up RTP receiver: {e}")
            self.stop()
            return False
    
    def stop(self):
        """Stop the RTP receiver."""
        # Stop all tone generators
        for tone_id in list(self.tone_generators.keys()):
            self._stop_tone(tone_id)
        
        # Stop receive threads
        self.running = False
        for port, thread in self.receive_threads.items():
            if thread:
                thread.join(timeout=2.0)
        self.receive_threads = {}
        
        # Close all sockets
        for port, sock in self.sockets.items():
            if sock:
                sock.close()
        self.sockets = {}
        
        # Shut down audio
        if self.server:
            try:
                self.server.stop()
                self.server.shutdown()
            except Exception as e:
                logger.warning(f"Error during server shutdown: {e}")
            self.server = None
            
        logger.info("RTP receiver stopped")
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
        self.audio_buffers = {}  # ssrc -> numpy buffer queue
        
        # RTP processing
        self.last_sequence = {}  # ssrc -> last sequence number
        
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
    
    def _process_audio_packet(self, ssrc, sequence_number, timestamp, payload):
        """Process an audio packet.
        
        Args:
            ssrc (int): Synchronization source
            sequence_number (int): RTP sequence number
            timestamp (int): RTP timestamp
            payload (bytes): Audio payload
        """
        # Convert PCM bytes to numpy array
        audio_data = np.frombuffer(payload, dtype=np.int16).astype(np.float32) / 32767.0
        
        # Store in buffer for mixing/playback (simplified for MVP)
        worker_id = ssrc  # For the MVP, we'll use SSRC as worker ID
        
        # At this point, in a real implementation we would:
        # 1. Add the audio to a jitter buffer for the worker
        # 2. Check sequence numbers for packet loss
        # 3. Use timestamps for proper alignment
        # 4. Mix multiple worker streams
        
        # For the MVP, we'll just log that we received audio
        logger.info(f"Received {len(audio_data)/self.sr:.3f}s audio from worker {worker_id}")
        
        # Play the audio in real-time using pyo (if the server is running)
        if self.server is not None and self.server.getIsStarted():
            # For MVP we'll just generate a sine with the same pitch
            # In a real implementation, we would use the actual received audio
            middle_c_freq = 261.63
            s = Sine(freq=middle_c_freq, mul=0.3).out()
            
            logger.info(f"Playing audio from worker {worker_id}")
    
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
                              buffersize=self.buffer_size, duplex=1)
            self.server.setVerbosity(1)
            self.server.boot()
            self.server.start()
            
            logger.info(f"RTP receiver set up on port {port}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting up RTP receiver: {e}")
            self.stop()
            return False
    
    def stop(self):
        """Stop the RTP receiver."""
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
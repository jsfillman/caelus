#!/usr/bin/env python3
"""
RTP streaming module for Caelus K8s worker.
"""

import logging
import numpy as np
import socket
import struct
import threading
import time
import random

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RTPSender:
    """RTP audio sender."""
    
    def __init__(self, sr=44100):
        """Initialize RTP sender.
        
        Args:
            sr (int): Sample rate
        """
        self.sr = sr
        self.socket = None
        self.target_ip = None
        self.target_port = None
        self.sequence_number = 0
        self.timestamp = 0
        self.ssrc = random.randint(0, 0xFFFFFFFF)  # Random synchronization source
        logger.info("RTP sender initialized")
    
    def setup(self, ip, port):
        """Set up RTP streaming to a specific IP and port.
        
        Args:
            ip (str): IP address to stream to
            port (int): Port to stream to
        """
        self.target_ip = ip
        self.target_port = port
        
        # Close any existing socket
        if self.socket:
            self.socket.close()
        
        # Create UDP socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        logger.info(f"RTP stream setup for {ip}:{port}")
        return True
    
    def _create_rtp_packet(self, payload, timestamp):
        """Create an RTP packet.
        
        Args:
            payload (bytes): Audio payload
            timestamp (int): RTP timestamp
            
        Returns:
            bytes: RTP packet
        """
        # RTP header (12 bytes)
        # 0                   1                   2                   3
        # 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
        # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        # |V=2|P|X|  CC   |M|     PT      |       sequence number         |
        # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        # |                           timestamp                           |
        # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        # |           synchronization source (SSRC) identifier            |
        # +=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+
        
        version = 2
        padding = 0
        extension = 0
        cc = 0
        marker = 0
        payload_type = 11  # PCM audio
        
        byte1 = (version << 6) | (padding << 5) | (extension << 4) | cc
        byte2 = (marker << 7) | payload_type
        
        # Increment sequence number for each packet
        self.sequence_number = (self.sequence_number + 1) & 0xFFFF
        
        # Create header
        header = struct.pack(
            "!BBHII",
            byte1,
            byte2,
            self.sequence_number,
            timestamp,
            self.ssrc
        )
        
        # Combine header and payload
        return header + payload
    
    def stream_buffer(self, buffer):
        """Stream an audio buffer over RTP.
        
        Args:
            buffer (numpy.ndarray): Audio buffer to stream
        """
        if not self.socket or not self.target_ip or not self.target_port:
            logger.error("RTP socket not set up")
            return False
        
        try:
            # Convert float32 audio to int16 PCM
            pcm_data = (buffer * 32767).astype(np.int16)
            
            # Convert to bytes
            payload = pcm_data.tobytes()
            
            # Create RTP packet
            timestamp = int(time.time() * self.sr)  # Sample-based timestamp
            packet = self._create_rtp_packet(payload, timestamp)
            
            # Send packet
            self.socket.sendto(packet, (self.target_ip, self.target_port))
            
            duration = len(buffer) / self.sr
            logger.info(f"Streamed {duration:.2f}s buffer to {self.target_ip}:{self.target_port}")
            return True
        
        except Exception as e:
            logger.error(f"Error streaming buffer: {e}")
            return False
        
    def close(self):
        """Close the RTP stream."""
        if self.socket:
            self.socket.close()
            self.socket = None
        
        self.target_ip = None
        self.target_port = None
        logger.info("RTP stream closed")
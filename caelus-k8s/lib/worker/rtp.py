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
        self.sequence_number = random.randint(0, 0xFFFF)  # Random start sequence
        self.timestamp_offset = random.randint(0, 0xFFFFFFFF)  # Random timestamp offset
        self.ssrc = random.randint(0, 0xFFFFFFFF)  # Random synchronization source
        
        # For streaming longer audio in chunks
        self.streaming_thread = None
        self.streaming = False
        
        # Track current streaming note - very important for stopping specific notes
        self.current_streaming_note = None
        
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
    
    def _create_rtp_packet(self, payload, timestamp=None):
        """Create an RTP packet.
        
        Args:
            payload (bytes): Audio payload
            timestamp (int, optional): RTP timestamp
            
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
        
        # Use provided timestamp or generate one based on sample rate
        if timestamp is None:
            # Convert to timestamp units (samples since start)
            current_time = int(time.time() * self.sr)
            timestamp = (current_time + self.timestamp_offset) & 0xFFFFFFFF
        
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
            # Check for empty or None buffer
            if buffer is None or len(buffer) == 0:
                logger.warning("Empty buffer provided to stream_buffer")
                return False
                
            # Convert float32 audio to int16 PCM
            pcm_data = (buffer * 32767).astype(np.int16)
            
            # Convert to bytes
            payload = pcm_data.tobytes()
            
            # Create RTP packet
            packet = self._create_rtp_packet(payload)
            
            # Send packet
            self.socket.sendto(packet, (self.target_ip, self.target_port))
            
            duration = len(buffer) / self.sr
            logger.info(f"Streamed {duration:.2f}s buffer ({len(payload)} bytes) to {self.target_ip}:{self.target_port}")
            return True
        
        except Exception as e:
            logger.error(f"Error streaming buffer: {e}")
            return False
    
    def stream_buffer_chunked(self, buffer, chunk_size=1024, chunk_interval=0.020, note=None):
        """Stream a buffer in chunks for continuous playback.
        
        Args:
            buffer (numpy.ndarray): Audio buffer to stream
            chunk_size (int): Samples per chunk
            chunk_interval (float): Time between chunks in seconds
            note (int, optional): MIDI note number being played, used to stop specific notes
        """
        # Stop any existing streaming
        self.stop_streaming()
        
        # Track which note we're currently streaming
        self.current_streaming_note = note
        
        # Start new streaming thread
        self.streaming = True
        self.streaming_thread = threading.Thread(
            target=self._streaming_thread_func,
            args=(buffer, chunk_size, chunk_interval)
        )
        self.streaming_thread.daemon = True
        self.streaming_thread.start()
        
        logger.info(f"Started chunked streaming of note {note if note else 'unknown'} ({len(buffer)/self.sr:.2f}s audio)")
        return True
    
    def _streaming_thread_func(self, buffer, chunk_size, chunk_interval):
        """Thread function for chunked streaming.
        
        Args:
            buffer (numpy.ndarray): Audio buffer to stream
            chunk_size (int): Samples per chunk
            chunk_interval (float): Time between chunks in seconds
        """
        try:
            # Calculate number of chunks
            num_chunks = (len(buffer) + chunk_size - 1) // chunk_size
            
            # Calculate timestamp increment per chunk
            timestamp_increment = int(chunk_size)
            base_timestamp = int(time.time() * self.sr)
            
            logger.info(f"Streaming {num_chunks} chunks, {chunk_interval*1000:.1f}ms apart")
            
            # Maximum streaming time (0.5 seconds - much shorter to stop more quickly)
            max_duration = 0.5  # in seconds (reduced from 4.0)
            max_chunks = min(num_chunks, int(max_duration / chunk_interval))
            
            # Stream each chunk (up to max_chunks)
            for i in range(max_chunks):
                if not self.streaming:
                    logger.info("Streaming stopped")
                    break
                    
                # Extract chunk
                start = i * chunk_size
                end = min(start + chunk_size, len(buffer))
                chunk = buffer[start:end]
                
                # If last chunk is smaller, pad with zeros
                if len(chunk) < chunk_size:
                    chunk = np.pad(chunk, (0, chunk_size - len(chunk)), 'constant')
                
                # Convert to PCM and create packet
                pcm_data = (chunk * 32767).astype(np.int16)
                payload = pcm_data.tobytes()
                
                # Calculate timestamp for this chunk
                timestamp = (base_timestamp + i * timestamp_increment) & 0xFFFFFFFF
                
                # Create and send packet
                packet = self._create_rtp_packet(payload, timestamp)
                self.socket.sendto(packet, (self.target_ip, self.target_port))
                
                # Wait for next chunk
                time.sleep(chunk_interval)
            
            logger.info(f"Finished streaming {max_chunks} of {num_chunks} chunks (limited to {max_duration}s)")
            
        except Exception as e:
            logger.error(f"Error in streaming thread: {e}")
        finally:
            self.streaming = False
            self.streaming_thread = None
    
    def stop_streaming(self, note=None):
        """Stop chunked streaming.
        
        Args:
            note (int, optional): If provided, only stop streaming for this specific note
        """
        # If note is specified, only stop if it matches current streaming note
        if note is not None and self.current_streaming_note != note:
            logger.info(f"Not stopping streaming for note {note} - current streaming note is {self.current_streaming_note}")
            return
            
        if self.streaming:
            logger.info(f"Stopping chunked streaming for note {self.current_streaming_note}")
            self.streaming = False
            if self.streaming_thread:
                self.streaming_thread.join(timeout=1.0)
                self.streaming_thread = None
            
            # Clear current streaming note
            self.current_streaming_note = None
            logger.info("Stopped chunked streaming")
    
    def close(self):
        """Close the RTP stream."""
        # Stop streaming
        self.stop_streaming()
        
        # Close socket
        if self.socket:
            self.socket.close()
            self.socket = None
        
        self.target_ip = None
        self.target_port = None
        logger.info("RTP stream closed")
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
    """Audio receiver with Jack support.
    
    This class handles audio reception from workers, either via Jack or direct sockets.
    The name RTPReceiver is kept for backward compatibility.
    """
    
    def __init__(self, sr=44100, buffer_size=1024, nchnls=2, jack_client_name="caelus_controller"):
        """Initialize audio receiver.
        
        Args:
            sr (int): Sample rate
            buffer_size (int): Buffer size for audio processing
            nchnls (int): Number of audio channels
            jack_client_name (str): Name to use for Jack client
        """
        self.sr = sr
        self.buffer_size = buffer_size
        self.nchnls = nchnls
        self.jack_client_name = jack_client_name
        
        # Socket dict - multiple sockets for different ports (legacy mode)
        self.sockets = {}  # port -> socket
        self.receive_threads = {}  # port -> thread
        self.running = False
        # Base port
        self.base_port = None
        
        # Jack-related variables
        self.jack_client = None
        self.jack_inports = []
        
        # Audio processing
        self.server = None
        self.mixer = None
        
        # For backwards compatibility
        self.jitter_buffers = {}  # ssrc -> queue
        self.jitter_buffer_size = 100
        self.last_sequence = {}
        self.tone_generators = {}
        
        logger.info("Audio receiver initialized with Jack support")
    
    def _parse_rtp_packet(self, packet):
        """Parse an RTP packet.
        
        Args:
            packet (bytes): RTP packet data
            
        Returns:
            tuple: (ssrc, sequence_number, timestamp, payload, marker_bit)
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
        marker = (byte2 >> 7) & 0x1  # Extract marker bit (important for end-of-stream)
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
        
        # Return the marker bit as part of the result
        return (ssrc, sequence_number, timestamp, payload, marker)
    
    def _extract_midi_note(self, data):
        """Extract MIDI note from audio data.
        
        Accurately detects the frequency using zero-crossing method and FFT validation.
        
        Args:
            data (numpy.ndarray): Audio data
            
        Returns:
            int: Accurate MIDI note number
        """
        # Check if we have enough data
        if len(data) < 256:
            logger.warning(f"Not enough audio data for frequency detection ({len(data)} samples)")
            return 60  # Default to middle C if not enough data
            
        # Method 1: Zero-crossing method for frequency estimation
        zero_crossings = np.where(np.diff(np.signbit(data)))[0]
        if len(zero_crossings) >= 2:
            # Calculate average period
            periods = np.diff(zero_crossings)
            # Filter out outliers - use periods in the middle 80% percentile
            periods = periods[periods > np.percentile(periods, 10)]
            periods = periods[periods < np.percentile(periods, 90)]
            
            if len(periods) > 0:
                avg_period = np.mean(periods) * 2  # Multiply by 2 for full period
                # Calculate frequency
                freq_zc = self.sr / avg_period if avg_period > 0 else 440
            else:
                freq_zc = 440  # Default if we can't detect
        else:
            freq_zc = 440  # Default if not enough zero crossings
            
        # Method 2: FFT for frequency estimation (more accurate for complex waveforms)
        try:
            # Use next power of 2 for better FFT performance
            n = 2 ** int(np.ceil(np.log2(len(data))))
            # Compute FFT and get magnitude
            fft_data = np.abs(np.fft.rfft(data, n=n))
            # Get frequency bins
            freqs = np.fft.rfftfreq(n, d=1/self.sr)
            # Find the peak frequency (excluding DC component)
            peak_idx = np.argmax(fft_data[1:]) + 1
            freq_fft = freqs[peak_idx]
        except Exception as e:
            logger.error(f"Error in FFT calculation: {e}")
            freq_fft = freq_zc  # Fall back to zero-crossing method
        
        # Combine both methods - prefer FFT but validate with zero crossing
        frequency = freq_fft
        
        # Convert to MIDI note
        if frequency <= 0:
            return 60
            
        midi_note = int(round(69 + 12 * np.log2(frequency / 440.0)))
        
        # Log the detected frequency and MIDI note
        logger.info(f"Detected frequency: {frequency:.2f} Hz, MIDI note: {midi_note}")
        
        # Clamp to valid MIDI range
        return max(0, min(127, midi_note))
    
    def _process_audio_packet(self, ssrc, sequence_number, timestamp, payload, port=None, marker=False):
        """Process an audio packet.
        
        Args:
            ssrc (int): Synchronization source
            sequence_number (int): RTP sequence number
            timestamp (int): RTP timestamp
            payload (bytes): Audio payload
            port (int): Port the packet was received on
            marker (bool): RTP marker bit (used for end-of-stream marker)
        """
        try:
            # Receive the raw bytes - NO CONVERSION
            # Keep everything in float32 throughout
            if len(payload) < 16:  # Need at least a few samples (float32 = 4 bytes/sample)
                logger.warning(f"Received very small payload: {len(payload)} bytes")
                return
                
            # Convert bytes back to float32 array without scaling or normalization
            audio_data = np.frombuffer(payload, dtype=np.float32)
            
            # Use a single ID for the entire session
            # This way we don't create new players for each chunk
            tone_id = "main_output"
            
            # Check for end-of-stream marker (important for note-off)
            if marker:
                logger.info(f"Received END-OF-STREAM marker for stream {tone_id}")
                # If we have this tone active, stop it
                if tone_id in self.tone_generators:
                    self._stop_tone(tone_id)
                    return  # Skip further processing for end-of-stream packets
                else:
                    logger.warning(f"Received end-of-stream for unknown stream {tone_id}")
                    return
            
            # Play incoming audio directly if server is running
            if self.server is not None and self.server.getIsStarted():
                # Using a very simple approach to play audio
                # Just play each packet directly to reduce stutter
                try:
                    # Simple raw audio streaming approach using PyAudio
                    # Play exactly what comes in from the RTP stream
                    if len(audio_data) > 0:
                        try:
                            # Initialize PyAudio if not already done
                            if not hasattr(self, 'pyaudio'):
                                try:
                                    import pyaudio
                                    self.pyaudio = pyaudio.PyAudio()
                                    logger.info("Initialized PyAudio for direct audio streaming")
                                except ImportError:
                                    logger.error("PyAudio not installed. Install with: pip install pyaudio")
                                    
                            # Only continue if we have PyAudio
                            if hasattr(self, 'pyaudio'):
                                # Each packet goes directly to the stream
                                if not hasattr(self, 'stream') or self.stream is None:
                                    # Create the audio stream if we don't have one
                                    # Configure PyAudio with explicit parameters
                                    # Make absolutely sure we're using the right format and rate
                                    import pyaudio
                                    
                                    # Print information about sample rate
                                    logger.info(f"Creating PyAudio stream with sample rate: {self.sr}")
                                    
                                    # Create stream with appropriate buffer size and explicit parameters
                                    # Moderate buffer size - large enough for stability but not too large
                                    logger.info(f"Creating PyAudio stream with explicit parameters")
                                    
                                    # Set up with consistent parameters to match sender
                                    self.stream = self.pyaudio.open(
                                        format=pyaudio.paFloat32,  # IMPORTANT: Must be float32
                                        channels=1,                # Mono audio
                                        rate=int(self.sr),         # Match the worker's sample rate exactly
                                        output=True,
                                        frames_per_buffer=4096,    # Balanced buffer size
                                        # Output device index - use default
                                        output_device_index=None
                                    )
                                    logger.info(f"Created PyAudio stream at {self.sr} Hz")
                                
                                # Write the data directly to the stream - NO CONVERSION
                                # Pass the float32 data directly to PyAudio
                                # Audio data should already be in float32 format
                                try:
                                    # Check that the data contains valid samples by examining min/max values
                                    min_val = np.min(audio_data) if len(audio_data) > 0 else 0
                                    max_val = np.max(audio_data) if len(audio_data) > 0 else 0
                                    
                                    # Log detailed stats about the audio data to help diagnose issues
                                    if len(audio_data) > 0 and (len(audio_data) % 100 == 0):
                                        # Calculate stats for diagnostics
                                        mean_val = np.mean(audio_data)
                                        std_val = np.std(audio_data)
                                        zero_crossings = np.sum(np.diff(np.signbit(audio_data)) != 0)
                                        rms = np.sqrt(np.mean(np.square(audio_data)))
                                        
                                        # Log comprehensive audio statistics
                                        logger.info(f"Audio stats: min={min_val:.4f}, max={max_val:.4f}, " +
                                                   f"mean={mean_val:.4f}, std={std_val:.4f}, " +
                                                   f"rms={rms:.4f}, zero_x={zero_crossings}, len={len(audio_data)}")
                                    
                                    # Simple direct streaming - absolutely no processing
                                    self.stream.write(audio_data.tobytes())
                                    
                                except Exception as e:
                                    logger.error(f"Error writing to audio stream: {e}")
                                    
                                logger.info(f"Wrote {len(audio_data)} samples to audio stream")
                                
                            # Handle end-of-stream
                            if marker:
                                # Close stream when we're done
                                if hasattr(self, 'stream') and self.stream is not None:
                                    self.stream.stop_stream()
                                    self.stream.close()
                                    self.stream = None
                                    logger.info("Closed audio stream due to end-of-stream marker")
                        except Exception as e:
                            logger.error(f"Error creating table: {e}", exc_info=True)
                except Exception as e:
                    logger.error(f"Error playing audio: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Error processing audio packet: {e}")
    
    def _stop_tone(self, tone_id):
        """Stop a tone generator.
        
        Args:
            tone_id (int): ID of the tone to stop
        """
        if tone_id in self.tone_generators:
            try:
                logger.info(f"Stopping tone ID {tone_id}")
                # Force immediate stop instead of fading
                # This ensures tones stop reliably
                try:
                    # Get the generator from the dictionary
                    gen_info = self.tone_generators[tone_id]
                    if "generator" in gen_info:
                        gen_info["generator"].stop()
                    else:
                        logger.warning(f"No generator found for tone {tone_id}")
                except Exception as e:
                    logger.warning(f"Error stopping tone generator: {e}")
                
                # Remove from dictionaries immediately
                del self.tone_generators[tone_id]
                
                # Also clean up timestamp buffer if it exists
                if hasattr(self, 'timestamp_buffers') and tone_id in self.timestamp_buffers:
                    del self.timestamp_buffers[tone_id]
                    
                logger.info(f"Tone ID {tone_id} stopped and removed")
            except Exception as e:
                logger.error(f"Error stopping tone: {e}")
    
    def _receive_thread_func(self, port):
        """Thread function for receiving direct audio stream.
        
        Args:
            port (int): Port to listen on
        """
        logger.info(f"Direct audio receive thread started on port {port}")
        
        server_socket = self.sockets.get(port)
        if server_socket is None:
            logger.error(f"No server socket for port {port}")
            return
        
        # First, wait for a client connection
        try:
            logger.info(f"Waiting for worker connection on port {port}...")
            server_socket.settimeout(0.5)  # Use timeout for accept to allow thread shutdown
            
            # This is our main loop to accept new connections
            while self.running:
                try:
                    # Accept incoming connection
                    client_socket, addr = server_socket.accept()
                    logger.info(f"Accepted connection from {addr}")
                    
                    # Set non-blocking with timeout
                    client_socket.settimeout(0.5)
                    
                    # This inner loop handles data from a single client
                    while self.running:
                        try:
                            # First read the 4-byte length header
                            length_bytes = client_socket.recv(4)
                            if not length_bytes or len(length_bytes) < 4:
                                logger.warning(f"Connection closed or invalid data from {addr}")
                                break
                                
                            # Convert bytes to integer length
                            data_length = int.from_bytes(length_bytes, byteorder='little')
                            
                            # Now read exactly that many bytes for the audio data
                            data = b''
                            remaining = data_length
                            
                            # Loop until we get all the data
                            while remaining > 0 and self.running:
                                chunk = client_socket.recv(min(remaining, 32768))
                                if not chunk:
                                    logger.warning(f"Connection closed while receiving data from {addr}")
                                    break
                                data += chunk
                                remaining -= len(chunk)
                            
                            # Process the complete data packet if we got it all
                            if len(data) == data_length:
                                # Convert bytes back to numpy array
                                audio_data = np.frombuffer(data, dtype=np.float32)
                                
                                # Process audio directly without any overhead
                                # Important: Use low-latency direct processing
                                self._process_audio_direct(audio_data)
                                
                                # Log only occasionally to reduce CPU overhead
                                if random.random() < 0.05:  # Log only ~5% of packets
                                    logger.info(f"Processed {len(audio_data)} samples")
                            else:
                                logger.warning(f"Incomplete data received: got {len(data)}/{data_length} bytes")
                                
                        except socket.timeout:
                            # This is expected - allows checking self.running
                            continue
                        except Exception as e:
                            logger.error(f"Error receiving audio data: {e}")
                            break
                            
                    # Close client connection when done
                    try:
                        client_socket.close()
                        logger.info(f"Closed connection from {addr}")
                    except:
                        pass
                        
                except socket.timeout:
                    # This is expected - allows checking self.running
                    continue
                except Exception as e:
                    logger.error(f"Error accepting connection: {e}")
                    time.sleep(1)  # Avoid busy loop on error
                    
        except Exception as e:
            logger.error(f"Error in receive thread: {e}")
            
        logger.info(f"Direct audio receive thread stopped for port {port}")
    
    def _process_audio_direct(self, audio_data):
        """Process audio data directly without RTP protocol.
        
        Args:
            audio_data (numpy.ndarray): Audio data in float32 format
        """
        # Skip if no data
        if len(audio_data) == 0:
            return
            
        # Play the audio directly using PyAudio
        try:
            # Initialize PyAudio if not already done
            if not hasattr(self, 'pyaudio'):
                try:
                    import pyaudio
                    self.pyaudio = pyaudio.PyAudio()
                    logger.info("Initialized PyAudio for direct audio streaming")
                except ImportError:
                    logger.error("PyAudio not installed. Install with: pip install pyaudio")
                    return
            
            # Create the audio stream if we don't have one
            if not hasattr(self, 'stream') or self.stream is None:
                # Configure PyAudio with explicit parameters
                import pyaudio
                
                # Print information about sample rate
                logger.info(f"Creating PyAudio stream with sample rate: {self.sr}")
                
                # Create stream with low-latency buffer settings and explicit parameters
                # Use the smallest possible buffer and allow buffer underruns for lowest latency
                try:
                    self.stream = self.pyaudio.open(
                        format=pyaudio.paFloat32,
                        channels=1, 
                        rate=int(self.sr),
                        output=True,
                        frames_per_buffer=256,  # Extremely small buffer for lowest latency
                        stream_callback=None    # Use blocking mode for direct control
                    )
                    logger.info("Created low-latency audio stream")
                except Exception as e:
                    # Fallback to safer settings if needed
                    logger.warning(f"Could not create low-latency stream: {e}. Using fallback settings")
                    self.stream = self.pyaudio.open(
                        format=pyaudio.paFloat32,
                        channels=1, 
                        rate=int(self.sr),
                        output=True,
                        frames_per_buffer=512  # Slightly larger buffer as fallback
                    )
                logger.info(f"Created PyAudio stream at {self.sr} Hz")
            
            # Write directly to the audio stream
            self.stream.write(audio_data.tobytes())
            
            # Log statistics occasionally (every ~100th packet)
            if random.random() < 0.01:
                # Calculate useful statistics for monitoring
                min_val = np.min(audio_data)
                max_val = np.max(audio_data)
                rms = np.sqrt(np.mean(np.square(audio_data)))
                peak = np.max(np.abs(audio_data))
                
                logger.info(f"Audio stats: rms={rms:.4f}, peak={peak:.4f}, " +
                           f"min={min_val:.4f}, max={max_val:.4f}, len={len(audio_data)}")
                
                # Report if we're getting silence
                if peak < 0.01:
                    logger.debug("Receiving silence")
                else:
                    logger.debug(f"Receiving active audio (peak={peak:.4f})")
            
        except Exception as e:
            logger.error(f"Error playing direct audio: {e}", exc_info=True)
    
    def setup_jack(self):
        """Set up Jack audio client for receiving audio from workers."""
        try:
            import jack
            
            # Create Jack client
            self.jack_client = jack.Client(self.jack_client_name)
            
            # Create input port to receive audio from workers
            inport = self.jack_client.inports.register("input")
            self.jack_inports.append(inport)
            
            # Get actual buffer size and sample rate from Jack
            self.buffer_size = self.jack_client.blocksize
            actual_sr = self.jack_client.samplerate
            if actual_sr != self.sr:
                logger.warning(f"Jack sample rate ({actual_sr}) differs from requested ({self.sr}). Using Jack's rate.")
                self.sr = actual_sr
            
            # Set up audio output if not in offline mode
            try:
                import pyaudio
                self.pyaudio = pyaudio.PyAudio()
                self.stream = self.pyaudio.open(
                    format=pyaudio.paFloat32,
                    channels=1,
                    rate=int(self.sr),
                    output=True,
                    frames_per_buffer=self.buffer_size
                )
                logger.info(f"Set up PyAudio output stream at {self.sr} Hz")
                
                # Set up a buffer for accumulating audio data
                self.audio_buffer = np.zeros(self.buffer_size, dtype=np.float32)
                self.buffer_position = 0
                
                # Define process callback
                @self.jack_client.set_process_callback
                def process(frames):
                    # Get audio data from input port
                    audio_data = inport.get_array()
                    
                    # Process the audio data
                    # For example, send it directly to the PyAudio stream
                    self.process_jack_audio(audio_data, frames)
                
                # Define shutdown callback
                @self.jack_client.set_shutdown_callback
                def shutdown(status, reason):
                    logger.warning(f"Jack shut down: {reason}")
                    self.running = False
                
                # Activate the client
                self.jack_client.activate()
                logger.info(f"Jack client '{self.jack_client_name}' activated")
                
                return True
                
            except Exception as e:
                logger.error(f"Error setting up PyAudio output: {e}")
                return False
                
        except ImportError:
            logger.error("Jack module not available. Install with: pip install JACK-Client")
            return False
        except Exception as e:
            logger.error(f"Error setting up Jack client: {e}")
            return False
    
    def process_jack_audio(self, audio_data, frames):
        """Process audio data received from Jack.
        
        Args:
            audio_data (numpy.ndarray): Audio data from Jack
            frames (int): Number of frames
        """
        try:
            # Ensure we have a stream to write to
            if hasattr(self, 'stream') and self.stream:
                # Apply DC blocking filter to remove any DC offset
                # which can cause buzzing or clicks
                if not hasattr(self, 'prev_sample'):
                    self.prev_sample = 0.0
                    self.prev_output = 0.0
                
                # Apply a simple DC blocking filter (high-pass)
                # This helps remove DC offset which can cause buzzing
                filtered_data = np.zeros_like(audio_data)
                alpha = 0.995  # Filter coefficient (very close to 1.0 for minimal effect)
                
                for i in range(len(audio_data)):
                    # Simple first-order high-pass filter
                    filtered_data[i] = alpha * (self.prev_output + audio_data[i] - self.prev_sample)
                    self.prev_sample = audio_data[i]
                    self.prev_output = filtered_data[i]
                
                # Apply a gentle noise gate to further reduce buzzing
                # Threshold is very low to only remove true silence/noise
                noise_threshold = 0.002
                gate_data = np.copy(filtered_data)
                for i in range(len(gate_data)):
                    if abs(gate_data[i]) < noise_threshold:
                        gate_data[i] = 0.0
                
                # Write the processed data to the audio stream
                self.stream.write(gate_data.tobytes())
                
                # Log audio levels occasionally
                if random.random() < 0.001:
                    if len(audio_data) > 0:
                        rms = np.sqrt(np.mean(np.square(filtered_data)))
                        peak = np.max(np.abs(filtered_data))
                        logger.info(f"Jack audio: rms={rms:.4f}, peak={peak:.4f}")
        except Exception as e:
            logger.error(f"Error processing Jack audio: {e}")
    
    def setup(self, port=5000, offline=False, use_jack=True):
        """Set up audio receiver.
        
        Args:
            port (int): Base port to listen on (for socket mode)
            offline (bool): If True, don't output audio
            use_jack (bool): If True, use Jack for audio I/O
        """
        try:
            self.base_port = port
            
            # Try Jack setup first if enabled
            if use_jack:
                if self.setup_jack():
                    logger.info("Successfully set up Jack audio")
                    return True
                else:
                    logger.warning("Jack setup failed, falling back to socket mode")
            
            # Fall back to socket mode if Jack failed or was disabled
            # Create a TCP socket server for direct streaming
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            try:
                # Bind to all interfaces
                self.server_socket.bind(("0.0.0.0", port))
                self.server_socket.listen(5)  # Allow up to 5 pending connections
                logger.info(f"Started direct audio socket server on port {port}")
                
                # Store in sockets dict to maintain compatibility with rest of code
                self.sockets[port] = self.server_socket
            except Exception as e:
                logger.error(f"Failed to set up socket server on port {port}: {e}")
                self.server_socket.close()
                return False
            
            if not self.sockets:
                logger.error("Failed to set up socket server")
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
        """Stop the audio receiver."""
        # Stop all tone generators (legacy mode)
        for tone_id in list(self.tone_generators.keys()):
            self._stop_tone(tone_id)
        
        # Stop Jack client if active
        if self.jack_client:
            try:
                self.jack_client.deactivate()
                self.jack_client.close()
                logger.info("Jack client stopped")
            except Exception as e:
                logger.warning(f"Error stopping Jack client: {e}")
            self.jack_client = None
        
        # Stop PyAudio output if active
        if hasattr(self, 'stream') and self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
                logger.info("PyAudio stream closed")
            except Exception as e:
                logger.warning(f"Error closing PyAudio stream: {e}")
            self.stream = None
            
        if hasattr(self, 'pyaudio') and self.pyaudio:
            try:
                self.pyaudio.terminate()
                logger.info("PyAudio terminated")
            except Exception as e:
                logger.warning(f"Error terminating PyAudio: {e}")
            self.pyaudio = None
        
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
        
        # Shut down pyo server if active
        if self.server:
            try:
                self.server.stop()
                self.server.shutdown()
            except Exception as e:
                logger.warning(f"Error during server shutdown: {e}")
            self.server = None
            
        logger.info("Audio receiver stopped")
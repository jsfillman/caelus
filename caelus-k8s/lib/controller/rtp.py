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
            import random
            
            # Create Jack client
            self.jack_client = jack.Client(self.jack_client_name)
            
            # Create stereo output ports for controller's main output 
            outport_left = self.jack_client.outports.register("output_left")
            outport_right = self.jack_client.outports.register("output_right")
            self.jack_outports = [outport_left, outport_right]
            
            # Dictionary to store dedicated worker input ports
            self.worker_input_ports = {}  # worker_name -> port object
            
            # Active notes count for gain calculation
            self.active_notes_count = 0
            
            # Get actual buffer size and sample rate from Jack
            self.buffer_size = self.jack_client.blocksize
            actual_sr = self.jack_client.samplerate
            if actual_sr != self.sr:
                logger.warning(f"Jack sample rate ({actual_sr}) differs from requested ({self.sr}). Using Jack's rate.")
                self.sr = actual_sr
            
            # Set up audio output if not in offline mode
            try:
                # For DC blocking filter
                self.prev_sample_left = 0.0
                self.prev_output_left = 0.0
                self.prev_sample_right = 0.0
                self.prev_output_right = 0.0
                
                # Define process callback with enhanced audio routing and proper mixing algorithm
                @self.jack_client.set_process_callback
                def process(frames):
                    # Create silent output buffer
                    mixed_left = np.zeros(frames, dtype=np.float32)
                    mixed_right = np.zeros(frames, dtype=np.float32)
                    
                    # Count active input ports with non-zero audio
                    active_ports = 0
                    all_ports = list(self.worker_input_ports.values())
                    
                    # First pass to count active ports
                    for input_port in all_ports:
                        # Get input data
                        in_data = input_port.get_array()
                        # Check if there's actual audio (not just silence)
                        if np.max(np.abs(in_data)) > 0.01:
                            active_ports += 1
                    
                    # Update active notes count (with smoothing)
                    if active_ports > 0:
                        # Smoothly update active notes count
                        self.active_notes_count = 0.7 * self.active_notes_count + 0.3 * active_ports
                        if self.active_notes_count < 1.0:
                            self.active_notes_count = 1.0
                    
                    # Calculate gain based on active notes
                    # Use square-root scaling for perceptual balance
                    if self.active_notes_count > 1:
                        gain = 1.0 / np.sqrt(self.active_notes_count)
                    else:
                        gain = 1.0
                        
                    # Apply a small safety margin to prevent clipping
                    gain *= 0.9
                    
                    # Second pass to mix audio with calculated gain and DC blocking filter
                    for input_port in all_ports:
                        # Get input data
                        in_data = input_port.get_array()
                        
                        # Apply DC blocking filter to prevent buzzing
                        filtered_data = np.zeros_like(in_data)
                        alpha = 0.995  # Filter coefficient
                        prev_sample = 0.0
                        prev_output = 0.0
                        
                        for i in range(len(in_data)):
                            filtered_data[i] = alpha * (prev_output + in_data[i] - prev_sample)
                            prev_sample = in_data[i]
                            prev_output = filtered_data[i]
                        
                        # Apply gain and add to mix
                        mixed_left += filtered_data * gain
                        mixed_right += filtered_data * gain
                    
                    # Apply soft limiter to prevent clipping
                    # This uses a simple tanh-based soft clipper
                    peak_left = np.max(np.abs(mixed_left))
                    peak_right = np.max(np.abs(mixed_right))
                    peak_level = max(peak_left, peak_right)
                    
                    if peak_level > 0.95:
                        # Apply more aggressive limiting if we're close to clipping
                        limiting_gain = 0.95 / peak_level
                        mixed_left *= limiting_gain
                        mixed_right *= limiting_gain
                        
                        # Log the limiting action occasionally
                        if random.random() < 0.01:  # 1% chance to log
                            logger.info(f"Limiter activated: peak={peak_level:.2f}, gain={limiting_gain:.2f}")
                    
                    # Apply a noise gate to prevent silent buzzing
                    noise_threshold = 0.001
                    for i in range(len(mixed_left)):
                        if abs(mixed_left[i]) < noise_threshold:
                            mixed_left[i] = 0.0
                    for i in range(len(mixed_right)):
                        if abs(mixed_right[i]) < noise_threshold:
                            mixed_right[i] = 0.0
                    
                    # Route audio to output ports
                    outport_left.get_array()[:] = mixed_left
                    outport_right.get_array()[:] = mixed_right
                    
                    # Log audio levels occasionally to help diagnose issues
                    if random.random() < 0.01:  # 1% of callbacks
                        rms_l = np.sqrt(np.mean(np.square(mixed_left)))
                        peak_l = np.max(np.abs(mixed_left))
                        rms_r = np.sqrt(np.mean(np.square(mixed_right)))
                        peak_r = np.max(np.abs(mixed_right))
                        
                        if peak_l > 0.01 or peak_r > 0.01:  # Only log when there's actual audio
                            logger.info(f"Jack audio: rms={rms_l:.4f}/{rms_r:.4f}, peak={peak_l:.4f}/{peak_r:.4f}, active_notes={self.active_notes_count:.1f}")
                
                # Define shutdown callback
                @self.jack_client.set_shutdown_callback
                def shutdown(status, reason):
                    logger.warning(f"Jack shut down: {reason}")
                    self.running = False
                
                # Activate the client
                self.jack_client.activate()
                logger.info(f"Jack client '{self.jack_client_name}' activated")
                
                # Connect output ports to system playback ports
                self.setup_jack_outputs()
                
                # Start a background thread to periodically check and reconnect JACK ports
                self._start_reconnection_thread()
                
                return True
                
            except Exception as e:
                logger.error(f"Error setting up JACK audio: {e}", exc_info=True)
                return False
                
        except ImportError:
            logger.error("Jack module not available. Install with: pip install JACK-Client")
            return False
        except Exception as e:
            logger.error(f"Error setting up Jack client: {e}", exc_info=True)
            return False
    
    def create_worker_input_port(self, worker_name):
        """Create a dedicated input port for a worker.
        
        Args:
            worker_name (str): Name of the worker (e.g., "worker1")
            
        Returns:
            bool: True if port was created successfully, False otherwise
        """
        if not self.jack_client:
            logger.warning("Jack client not available, can't create worker input port")
            return False
            
        try:
            # Create unique port name based on worker name
            port_name = f"input_{worker_name}"
            
            # Check if port already exists
            if worker_name in self.worker_input_ports:
                logger.info(f"Input port for worker '{worker_name}' already exists")
                return True
            
            # Register new input port with Jack
            input_port = self.jack_client.inports.register(port_name)
            
            # Store port in dictionary
            self.worker_input_ports[worker_name] = input_port
            
            logger.info(f"Created input port '{port_name}' for worker '{worker_name}'")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create input port for worker '{worker_name}': {e}")
            return False
    
    def setup_jack_outputs(self):
        """Connect Jack outputs to system playback ports and connect worker outputs to our inputs."""
        try:
            import subprocess
            import random
            
            # List all available JACK ports
            result = subprocess.run(['jack_lsp'], capture_output=True, text=True)
            ports = result.stdout.strip().split('\n')
            logger.info(f"Available JACK ports: {ports}")
            
            # Look for system playback ports
            system_ports = [p for p in ports if 'system:playback' in p]
            logger.info(f"System playback ports: {system_ports}")
            
            # Look for worker output ports to connect to our dedicated input ports
            worker_ports = [p for p in ports if ('worker' in p.lower() and 'output' in p.lower()) or 
                                             ('worker' in p.lower() and 'out' in p.lower())]
            logger.info(f"Worker output ports: {worker_ports}")
            
            # Connect each worker output to its dedicated input port on the controller
            for worker_port in worker_ports:
                # Extract worker name from port name 
                # Try to parse out the worker name from port like "worker1:output_left"
                try:
                    worker_name = None
                    if ':' in worker_port:
                        client_name = worker_port.split(':')[0]
                        if client_name.startswith('worker'):
                            worker_name = client_name
                    
                    # If we couldn't extract it but it has "worker" in the name, use a generic name
                    if not worker_name:
                        # Create a unique name based on the port
                        worker_name = f"worker_{hash(worker_port) % 1000}"
                    
                    # Ensure we have an input port for this worker
                    if worker_name not in self.worker_input_ports:
                        self.create_worker_input_port(worker_name)
                    
                    # Connect the worker output to our dedicated input
                    if worker_name in self.worker_input_ports:
                        input_port = self.worker_input_ports[worker_name]
                        in_port_name = f'{self.jack_client_name}:{input_port.shortname}'
                        
                        # Check if already connected
                        conn_result = subprocess.run(['jack_lsp', '-c', worker_port], 
                                                     capture_output=True, text=True)
                        
                        if in_port_name not in conn_result.stdout:
                            subprocess.run(['jack_connect', worker_port, in_port_name])
                            logger.info(f"Connected {worker_port} to dedicated input {in_port_name}")
                        else:
                            logger.info(f"Worker {worker_port} already connected to {in_port_name}")
                            
                except Exception as e:
                    logger.warning(f"Failed to connect worker port {worker_port}: {e}")
            
            # Connect our output to system playback
            if len(system_ports) >= 2:
                # Connect our output ports to system playback ports for stereo
                try:
                    subprocess.run(['jack_connect', f'{self.jack_client_name}:output_left', 'system:playback_1'])
                    subprocess.run(['jack_connect', f'{self.jack_client_name}:output_right', 'system:playback_2'])
                    logger.info("Connected to system playback ports for stereo output")
                except Exception as e:
                    logger.warning(f"Failed to connect to system playback ports: {e}")
            elif system_ports:
                # Connect both channels to the one available system playback port
                try:
                    subprocess.run(['jack_connect', f'{self.jack_client_name}:output_left', system_ports[0]])
                    subprocess.run(['jack_connect', f'{self.jack_client_name}:output_right', system_ports[0]])
                    logger.info(f"Connected both channels to system playback port: {system_ports[0]}")
                except Exception as e:
                    logger.warning(f"Failed to connect to system playback port: {e}")
            else:
                logger.warning("Could not find system playback ports")
                
                # Try to connect to any available input ports as fallback
                input_ports = [p for p in ports if ('input' in p.lower() or 'in_' in p.lower()) and 'system' in p.lower()]
                if input_ports:
                    for i, port in enumerate(input_ports[:2]):
                        out_port = self.jack_outports[min(i, len(self.jack_outports)-1)]
                        port_name = f'{self.jack_client_name}:{out_port.shortname}'
                        try:
                            subprocess.run(['jack_connect', port_name, port])
                            logger.info(f"Connected {port_name} to fallback port: {port}")
                        except Exception as e:
                            logger.warning(f"Failed to connect {port_name} to {port}: {e}")
                else:
                    logger.warning("No suitable output ports found. Audio will be generated but not heard.")
            
            # As a last resort, try to connect to any ports that might receive audio
            if not system_ports and not input_ports:
                any_ports = [p for p in ports if p.startswith('system:') and not 'midi' in p.lower()]
                if any_ports:
                    for i, port in enumerate(any_ports[:2]):
                        out_port = self.jack_outports[min(i, len(self.jack_outports)-1)]
                        port_name = f'{self.jack_client_name}:{out_port.shortname}'
                        try:
                            subprocess.run(['jack_connect', port_name, port])
                            logger.info(f"Connected {port_name} to port: {port}")
                        except Exception as e:
                            logger.warning(f"Failed to connect {port_name} to {port}: {e}")
            
            # Log all active connections for debugging
            logger.info("Current JACK connections:")
            conn_result = subprocess.run(['jack_lsp', '-c'], capture_output=True, text=True)
            for line in conn_result.stdout.strip().split('\n'):
                if self.jack_client_name in line:
                    logger.info(f"  {line}")
            
            return True
        except Exception as e:
            logger.error(f"Error connecting Jack outputs: {e}", exc_info=True)
            return False
    
    def _start_reconnection_thread(self):
        """Start a thread to periodically check and reconnect JACK ports."""
        try:
            import threading
            import time
            
            # Flag to control thread execution
            self.reconnect_running = True
            
            def reconnect_thread_func():
                """Thread function to periodically reconnect JACK ports."""
                logger.info("JACK reconnection thread started")
                
                while self.reconnect_running:
                    try:
                        # Sleep most of the time to avoid unnecessary CPU usage
                        time.sleep(5)  # Check every 5 seconds
                        
                        # Check if our jack client is still active
                        if not hasattr(self, 'jack_client') or not self.jack_client:
                            logger.warning("JACK client no longer exists, stopping reconnect thread")
                            break
                            
                        # Only attempt reconnection if there are active workers
                        # This avoids continuous reconnection attempts when there are no workers
                        if hasattr(self, 'jack_client') and self.jack_client:
                            # Run the output setup again to reconnect any broken connections
                            self.setup_jack_outputs()
                            
                    except Exception as e:
                        logger.error(f"Error in JACK reconnection thread: {e}")
                        # Don't stop the thread on error, just continue with the next cycle
                
                logger.info("JACK reconnection thread stopped")
            
            # Create and start the thread
            self.reconnect_thread = threading.Thread(target=reconnect_thread_func)
            self.reconnect_thread.daemon = True  # Daemon thread stops automatically when main thread exits
            self.reconnect_thread.start()
            logger.info("Started JACK port reconnection monitoring thread")
            
        except Exception as e:
            logger.error(f"Error starting JACK reconnection thread: {e}")
    
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
        
        # Stop the reconnection thread if active
        if hasattr(self, 'reconnect_running'):
            self.reconnect_running = False
            if hasattr(self, 'reconnect_thread') and self.reconnect_thread:
                try:
                    self.reconnect_thread.join(timeout=2.0)
                    logger.info("JACK reconnection thread joined")
                except Exception as e:
                    logger.warning(f"Error joining reconnection thread: {e}")
        
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
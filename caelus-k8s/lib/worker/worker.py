#!/usr/bin/env python3
"""
Worker module for Caelus K8s.
"""

import logging
import argparse
import time
import threading
import random
import numpy as np
from pythonosc import dispatcher

from lib.common.osc import OSCServer, NOTE_ON, NOTE_OFF, WORKER_READY, WORKER_STATUS, AFTERTOUCH_POLY, AFTERTOUCH_CHANNEL
from lib.worker.oscillator import SineOscillator
from lib.worker.rtp import RTPSender

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CaelusWorker:
    """Caelus K8s worker that generates notes based on OSC messages."""
    
    def __init__(self, osc_ip="0.0.0.0", osc_port=9000, sample_rate=44100, max_polyphony=16, 
                 local_audio=False, use_pyo=False, jack_client_name="caelus_worker",
                 jack_connect_to=None, network_only=False):
        """Initialize the worker.
        
        Args:
            osc_ip (str): IP address to listen on for OSC
            osc_port (int): Port to listen on for OSC
            sample_rate (int): Audio sample rate
            max_polyphony (int): Maximum number of simultaneous notes
            local_audio (bool): If True, play audio locally instead of streaming
            use_pyo (bool): If True, use Pyo for direct audio (legacy mode)
            jack_client_name (str): Name to use for Jack client
            jack_connect_to (str): Jack port to connect to (optional)
        """
        self.osc_ip = osc_ip
        self.osc_port = osc_port
        self.use_pyo = use_pyo
        self.jack_client_name = jack_client_name
        self.jack_connect_to = jack_connect_to
        self.sample_rate = sample_rate
        self.max_polyphony = max_polyphony
        self.local_audio = local_audio
        self.network_only = network_only  # Store the network-only flag
        
        # Create oscillator and RTP sender
        self.oscillator = SineOscillator(sr=sample_rate)
        self.rtp_sender = RTPSender(sr=sample_rate)
        
        # Initialize Pyo server if local audio is enabled
        if self.local_audio:
            from pyo import Server
            self.audio_server = Server(sr=sample_rate, nchnls=2, buffersize=256)
            self.audio_server.boot()
            self.audio_server.start()
            logger.info("Local audio output enabled")
        
        # Create OSC server with custom dispatcher
        self.dispatcher = dispatcher.Dispatcher()
        self.dispatcher.map(NOTE_ON, self._handle_note_on)
        self.dispatcher.map(NOTE_OFF, self._handle_note_off)
        self.dispatcher.map(AFTERTOUCH_POLY, self._handle_aftertouch_poly)
        self.dispatcher.map(AFTERTOUCH_CHANNEL, self._handle_aftertouch_channel)
        self.dispatcher.map(WORKER_STATUS, self._handle_worker_status)
        
        self.osc_server = OSCServer(osc_ip, osc_port, self.dispatcher)
        
        # Keep track of active notes and controller connections
        self.active_notes = {}  # note number -> (freq, amp)
        self.controllers = {}   # controller IP -> (port, last_seen)
        
        # Note rendering thread
        self.render_thread = None
        self.running = False
        self.render_queue = []  # Queue of (note, velocity, controller_ip, port) tuples
        self.render_lock = threading.Lock()
        
        logger.info(f"Worker initialized on {osc_ip}:{osc_port}")
    
    def _handle_note_on(self, address, *args):
        """Handle note on OSC message.
        
        Args:
            address (str): OSC address
            *args: OSC arguments (note, velocity, rtp_port)
        """
        try:
            if len(args) < 3:
                logger.error(f"Not enough arguments for note_on: {args}")
                return
                
            note = args[0]
            velocity = args[1]
            rtp_port = args[2]
            
            # Get controller IP (sender of the OSC message)
            # In a real implementation, this would come from the OSC packet
            controller_ip = "127.0.0.1"  
            
            logger.info(f"Worker received NOTE ON: {note}, velocity: {velocity}, RTP port: {rtp_port}")
            
            # Store controller info
            self.controllers[controller_ip] = (rtp_port, time.time())
            
            # Check if we're at max polyphony
            if len(self.active_notes) >= self.max_polyphony:
                logger.warning(f"Maximum polyphony reached ({self.max_polyphony}), ignoring note {note}")
                return
            
            # Calculate frequency and amplitude
            frequency = self.oscillator.note_to_freq(note)
            amplitude = velocity/127.0
            
            # Store active note in both worker and oscillator
            self.active_notes[note] = (frequency, amplitude)
            self.oscillator.active_notes[note] = (frequency, amplitude)
            
            # Add to render queue
            with self.render_lock:
                self.render_queue.append((note, velocity, controller_ip, rtp_port))
            
        except Exception as e:
            logger.error(f"Error in _handle_note_on: {e}")
    
    def _handle_note_off(self, address, *args):
        """Handle note off OSC message.
        
        Args:
            address (str): OSC address
            *args: OSC arguments (note)
        """
        try:
            if len(args) < 1:
                logger.error(f"Not enough arguments for note_off: {args}")
                return
                
            note = args[0]
            logger.info(f"Note off: {note}")
            
            # Remove from active notes
            if note in self.active_notes:
                # Get controller IP (would come from OSC packet in real implementation)
                controller_ip = "127.0.0.1"
                rtp_port = self.controllers.get(controller_ip, (5000, 0))[0]
                
                # If local audio is enabled, stop the local sound
                if self.local_audio and hasattr(self, 'active_sounds') and note in self.active_sounds:
                    try:
                        # Stop the sound and remove from dictionary
                        self.active_sounds[note].stop()
                        del self.active_sounds[note]
                        logger.info(f"Stopped local playback for note {note}")
                    except Exception as e:
                        logger.error(f"Error stopping local sound for note {note}: {e}")
                
                # Generate release buffer
                # Store the note in oscillator.active_notes to prevent warnings
                if note not in self.oscillator.active_notes:
                    # Register the note in the oscillator using the same parameters
                    freq, amp = self.active_notes[note]
                    self.oscillator.active_notes[note] = (freq, amp)
                    
                release_buffer = self.oscillator.stop_note(note)
                
                # For local audio, removing from active_notes is sufficient
                # The audio thread will immediately stop playing the note
                # No need to send any data over the network
                    
                # Note is now completely released - nothing more to do
                # Socket connection is persistent and will be reused for the next note
                logger.info(f"Note {note} fully released")
                
                # Remove from active notes
                del self.active_notes[note]
                logger.info(f"Removed note {note} from active_notes dict (now: {list(self.active_notes.keys())})")
            else:
                logger.warning(f"Received note_off for inactive note: {note}")
        except Exception as e:
            logger.error(f"Error in _handle_note_off: {e}")
    
    def _handle_aftertouch_poly(self, address, *args):
        """Handle polyphonic aftertouch OSC message.
        
        Args:
            address (str): OSC address
            *args: OSC arguments (note, pressure)
        """
        try:
            if len(args) < 2:
                logger.error(f"Not enough arguments for poly aftertouch: {args}")
                return
                
            note = args[0]
            pressure = args[1]
            logger.info(f"Poly aftertouch: note={note}, pressure={pressure}")
            
            # Check if the note is playing
            if note in self.active_notes:
                # Get the current frequency and update the amplitude based on pressure
                frequency, _ = self.active_notes[note]
                
                # Scale the pressure to a reasonable amplitude range (0.1-1.0)
                # This ensures the note doesn't go completely silent at low pressure
                new_amplitude = 0.1 + (pressure / 127.0) * 0.9
                
                # Update the amplitude in our active_notes dictionary
                self.active_notes[note] = (frequency, new_amplitude)
                
                # Also update in the oscillator's active notes
                if hasattr(self.oscillator, 'active_notes'):
                    self.oscillator.active_notes[note] = (frequency, new_amplitude)
                
                logger.info(f"Updated amplitude for note {note} to {new_amplitude:.2f} from pressure {pressure}")
            else:
                logger.warning(f"Poly aftertouch for inactive note: {note}")
                
        except Exception as e:
            logger.error(f"Error in _handle_aftertouch_poly: {e}")
    
    def _handle_aftertouch_channel(self, address, *args):
        """Handle channel aftertouch OSC message.
        
        Args:
            address (str): OSC address
            *args: OSC arguments (pressure)
        """
        try:
            if len(args) < 1:
                logger.error(f"Not enough arguments for channel aftertouch: {args}")
                return
                
            pressure = args[0]
            logger.info(f"Channel aftertouch: pressure={pressure}")
            
            # Scale the pressure to a reasonable amplitude range (0.1-1.0)
            new_amplitude = 0.1 + (pressure / 127.0) * 0.9
            
            # Apply to all active notes
            for note in list(self.active_notes.keys()):
                frequency, _ = self.active_notes[note]
                
                # Update amplitude in our active_notes dictionary
                self.active_notes[note] = (frequency, new_amplitude)
                
                # Also update in the oscillator's active notes
                if hasattr(self.oscillator, 'active_notes'):
                    self.oscillator.active_notes[note] = (frequency, new_amplitude)
            
            note_count = len(self.active_notes)
            if note_count > 0:
                logger.info(f"Updated amplitude for all {note_count} active notes to {new_amplitude:.2f} from pressure {pressure}")
                
        except Exception as e:
            logger.error(f"Error in _handle_aftertouch_channel: {e}")

    def _handle_worker_status(self, address, *args):
        """Handle worker status request.
        
        Args:
            address (str): OSC address
            *args: OSC arguments (none expected)
        """
        try:
            # Get controller IP (would come from OSC packet in real implementation)
            controller_ip = "127.0.0.1"
            
            # Report current status
            active_note_count = len(self.active_notes)
            logger.info(f"Worker status requested by {controller_ip}: {active_note_count}/{self.max_polyphony} notes active")
            
            # In a real implementation, we would send a status response back to the controller
        except Exception as e:
            logger.error(f"Error in _handle_worker_status: {e}")
    
    def _render_thread_func(self):
        """Thread function for rendering and streaming audio."""
        logger.info("Audio render thread started")
        
        while self.running:
            try:
                # Process render queue
                to_render = None
                with self.render_lock:
                    if self.render_queue:
                        to_render = self.render_queue.pop(0)
                
                if to_render:
                    note, velocity, controller_ip, rtp_port = to_render
                    
                    # Set up RTP stream to controller
                    self.rtp_sender.setup(controller_ip, rtp_port)
                    
                    # Check if the note is still active (might have been turned off already)
                    if note not in self.active_notes:
                        logger.info(f"Note {note} already turned off, not rendering")
                        continue
                    
                    # Generate a simple initial buffer with appropriate envelope
                    # Use a small buffer size for minimal latency during attack
                    initial_duration = 0.1  # 100ms buffer for lower latency
                    frequency = self.oscillator.note_to_freq(note)
                    amplitude = velocity / 127.0 * 0.8  # Reduce amplitude slightly to prevent clipping
                    
                    # Generate continuous tone with an envelope to prevent clicks
                    t = np.linspace(0, initial_duration, int(self.sample_rate * initial_duration), False)
                    
                    # Create an envelope to prevent clicks (2ms fade in - very fast attack)
                    envelope = np.ones_like(t)
                    fade_samples = int(0.002 * self.sample_rate)  # 2ms - much faster attack
                    if len(t) > 2 * fade_samples:
                        # Apply fade in only (no fade out for sustained notes)
                        envelope[:fade_samples] = np.linspace(0, 1, fade_samples)
                        # Don't apply fade out for sustained notes
                    
                    # Generate a cleaner sine wave with simpler envelope for attack phase
                    attack_buffer = amplitude * np.sin(2 * np.pi * frequency * t) * envelope
                    
                    # Also create a longer sustain buffer that we'll loop
                    # This ensures sustained notes keep playing
                    sustain_duration = 0.5  # 500ms of sustained tone
                    t_sustain = np.linspace(0, sustain_duration, int(self.sample_rate * sustain_duration), False)
                    sustain_buffer = amplitude * np.sin(2 * np.pi * frequency * t_sustain)
                    
                    # Store both buffers for this note
                    self.note_buffers = getattr(self, 'note_buffers', {})
                    self.note_buffers[note] = (attack_buffer, sustain_buffer)
                    
                    # Use the attack buffer for immediate playback
                    audio_buffer = attack_buffer
                    
                    # Store the note information for the audio thread
                    # The audio thread will pick this up and start playing the note
                    logger.info(f"Note {note} activated: freq={frequency:.2f}Hz, amp={amplitude:.2f}")
                    
                    # If using local audio, Pyo direct method is left in place for compatibility
                    if self.local_audio and self.use_pyo:
                        from pyo import Sine
                        # Create a sine oscillator and play it directly with Pyo
                        sine = Sine(freq=float(frequency), mul=amplitude).out()
                        # Store in a dictionary to keep track of active sounds
                        if not hasattr(self, 'active_sounds'):
                            self.active_sounds = {}
                        self.active_sounds[note] = sine
                        logger.info(f"Playing note {note} directly with Pyo")
                else:
                    # Sleep a bit if no work to do
                    time.sleep(0.01)
                
            except Exception as e:
                logger.error(f"Error in render thread: {e}")
        
        logger.info("Audio render thread stopped")
    
    def register_with_controller(self, controller_ip, controller_port=8000):
        """Register this worker with a controller.
        
        Args:
            controller_ip (str): IP address of the controller
            controller_port (int): OSC port of the controller
        """
        try:
            # Create a client to communicate with the controller
            from lib.common.osc import OSCClient, WORKER_READY
            controller_client = OSCClient(controller_ip, controller_port)
            
            # For local testing, just use 127.0.0.1 directly
            my_ip = "127.0.0.1"
            
            # Uncomment this for production/networked deployment
            """
            # Use the machine's actual IP address, not 0.0.0.0
            import socket
            my_ip = socket.gethostbyname(socket.gethostname())
            if my_ip == "127.0.0.1":
                # Try to get a non-localhost IP
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                try:
                    # Doesn't have to be reachable
                    s.connect(('10.255.255.255', 1))
                    my_ip = s.getsockname()[0]
                except Exception:
                    pass
                finally:
                    s.close()
            """
            
            # IMPORTANT: Send the actual polyphony setting for this worker
            # Also send the JACK client name so controller can create dedicated input ports
            controller_client.client.send_message(WORKER_READY, [
                my_ip,                    # Worker IP
                self.osc_port,            # Worker OSC port
                self.max_polyphony,       # Worker note capacity
                self.jack_client_name     # JACK client name for audio routing
            ])
            logger.info(f"Registered with controller at {controller_ip}:{controller_port} with capacity={self.max_polyphony}, JACK={self.jack_client_name}")
            
            # Store controller info
            self.controllers[controller_ip] = (controller_port, time.time())
            
            return True
        except Exception as e:
            logger.error(f"Error registering with controller: {e}")
            return False

    def start(self, controller_ip=None, controller_port=8000):
        """Start the worker.
        
        Args:
            controller_ip (str, optional): IP of the controller to register with
            controller_port (int, optional): Port of the controller
        """
        # Start OSC server
        self.osc_server.start()
        
        # Start render thread
        self.running = True
        self.render_thread = threading.Thread(target=self._render_thread_func)
        self.render_thread.daemon = True
        self.render_thread.start()
        
        # Start Jack audio thread for all audio output (local and networked)
        self.audio_thread = threading.Thread(target=self._jack_thread_func)
        self.audio_thread.daemon = True
        self.audio_thread.start()
        
        if self.local_audio:
            logger.info("Started Jack thread with local audio output")
        else:
            logger.info("Started Jack thread with network streaming to controller")
            
        # Initialize Pyo server only if use_pyo is specifically enabled (legacy mode)
        if self.use_pyo:
            try:
                from pyo import Server
                self.audio_server = Server(sr=self.sample_rate, nchnls=2, buffersize=512, duplex=0)
                self.audio_server.boot()
                self.audio_server.start()
                logger.info("Started Pyo audio server (legacy mode)")
            except Exception as e:
                logger.error(f"Error starting Pyo audio server: {e}")
                self.use_pyo = False  # Disable Pyo on error
        
        # Register with controller if provided
        if controller_ip:
            self.register_with_controller(controller_ip, controller_port)
            
            # Set up periodic re-registration in case controller restarts
            def periodic_registration():
                while self.running:
                    self.register_with_controller(controller_ip, controller_port)
                    time.sleep(60)  # Re-register every minute
                    
            self.register_thread = threading.Thread(target=periodic_registration)
            self.register_thread.daemon = True
            self.register_thread.start()
        
        logger.info("Worker started with continuous note sustain enabled")
    
    def _jack_thread_func(self):
        """Thread function for JACK-based audio synthesis and network streaming.
        
        Uses JACK for professional audio handling and network streaming to controller.
        Can also operate in network-only mode without a local JACK server.
        """
        logger.info("Audio synthesis thread started")
        
        # If network-only mode is explicitly requested, skip JACK completely
        if self.network_only:
            logger.info("Network-only mode explicitly requested, skipping JACK")
            self._network_audio_engine()
            return
        
        # Check if JACK is available
        try:
            import jack
            use_jack = True
            logger.info("JACK module available, attempting to use JACK for audio")
        except ImportError:
            use_jack = False
            logger.info("JACK module not available, will use network streaming only")
            self._network_audio_engine()
            return
        
        # Check if JACK server is running
        if use_jack:
            try:
                import subprocess
                result = subprocess.run(['jack_lsp'], capture_output=True, text=True)
                if result.returncode != 0:
                    use_jack = False
                    logger.info("No JACK server running, will use network streaming only")
                    self._network_audio_engine()
                    return
            except Exception:
                use_jack = False
                logger.info("Could not check for JACK server, will use network streaming only")
                self._network_audio_engine()
                return
        
        # Audio parameters
        sample_rate = self.sample_rate
        buffer_size = 1024  # Default buffer size
        jack_client_name = self.jack_client_name
        
        # At this point we know JACK is available and server is running
        try:
            # Create the Jack client
            client = jack.Client(jack_client_name)
            
            # Register both left and right output ports (stereo audio output)
            outport_left = client.outports.register("output_left")
            outport_right = client.outports.register("output_right")
            
            # Get actual buffer size and sample rate from Jack
            buffer_size = client.blocksize
            actual_sr = client.samplerate
            if actual_sr != sample_rate:
                logger.warning(f"Jack sample rate ({actual_sr}) differs from requested ({sample_rate}). Using Jack's rate.")
                sample_rate = actual_sr
            
            logger.info(f"Connected to Jack server: buffer_size={buffer_size}, sample_rate={sample_rate}")
            
            # For phase continuity
            phase = {}  # note -> current phase
            
            # Define process callback - this is called by Jack when audio is needed
            @client.set_process_callback
            def process(frames):
                try:
                    # Get a snapshot of active notes to avoid mid-callback changes
                    current_active_notes = {}
                    if hasattr(self, 'active_notes'):
                        current_active_notes = dict(self.active_notes)
                    
                    # Create silent buffer
                    mixed_buffer = np.zeros(frames, dtype=np.float32)
                    
                    # Only process if we have active notes
                    if current_active_notes:
                        # Very rarely log debugging info
                        if random.random() < 0.001:  # 0.1% chance to log
                            logger.info(f"Processing audio for {len(current_active_notes)} notes: {list(current_active_notes.keys())}")
                            
                        # Count active notes for gain scaling
                        active_note_count = len(current_active_notes)
                        
                        # Calculate per-note gain using square-root scaling for perceptual balance
                        # VERY conservative settings to prevent clipping completely
                        if active_note_count > 1:
                            # Use square-root scaling for balanced polyphony, but with more conservative gain
                            note_gain = 0.4 / np.sqrt(active_note_count)
                        else:
                            note_gain = 0.4  # Even single notes should be quieter to prevent clipping
                        
                        # Log the gain calculation very infrequently
                        if random.random() < 0.0005:  # 0.05% chance to log
                            logger.info(f"Worker polyphony: {active_note_count} notes, gain={note_gain:.3f}")
                            
                        # Mix in all active notes with phase continuity
                        for note, (freq, amp) in current_active_notes.items():
                            # Ensure phase is initialized for this note
                            if note not in phase:
                                phase[note] = 0.0
                            
                            # Calculate phase increment per sample
                            phase_increment = 2 * np.pi * freq / sample_rate
                            
                            # Generate sine wave samples with current amplitude
                            note_buffer = np.zeros(frames, dtype=np.float32)
                            for i in range(frames):
                                note_buffer[i] = amp * np.sin(phase[note])
                                phase[note] += phase_increment
                                # Keep phase in sensible range to prevent floating point errors
                                while phase[note] >= 2 * np.pi:
                                    phase[note] -= 2 * np.pi
                            
                            # Apply the calculated gain and mix into the buffer
                            mixed_buffer += note_buffer * note_gain
                        
                        # Clean up phases for notes that are no longer active
                        for note in list(phase.keys()):
                            if note not in current_active_notes:
                                del phase[note]
                    
                    # Strict limiter to absolutely prevent clipping
                    max_amp = np.max(np.abs(mixed_buffer))
                    
                    # First stage limiting
                    if max_amp > 0.5:
                        target_amp = 0.5
                        gain = target_amp / max_amp
                        mixed_buffer *= gain
                    
                    # Second stage limiting (safety)
                    max_amp = np.max(np.abs(mixed_buffer))
                    if max_amp > 0.7:
                        gain = 0.7 / max_amp
                        mixed_buffer *= gain
                    
                    # Send to both Jack output ports (stereo output)
                    outport_left.get_array()[:] = mixed_buffer
                    outport_right.get_array()[:] = mixed_buffer
                    
                except Exception as e:
                    logger.error(f"Error in JACK process callback: {e}")
            
            # Define shutdown callback
            @client.set_shutdown_callback
            def shutdown(status, reason):
                logger.warning(f"Jack shut down: {reason}")
                self.running = False
            
            # Activate client
            client.activate()
            logger.info(f"JACK client activated for {jack_client_name}")
            
            # Try to connect to appropriate ports
            try:
                # Connect to specified port or auto-detect
                import subprocess
                
                if self.jack_connect_to:
                    # Connect to user-specified port
                    logger.info(f"Connecting to specified Jack port: {self.jack_connect_to}")
                    subprocess.run(['jack_connect', f'{jack_client_name}:output_left', self.jack_connect_to])
                    subprocess.run(['jack_connect', f'{jack_client_name}:output_right', self.jack_connect_to])
                    logger.info(f"Connected to port: {self.jack_connect_to}")
                else:
                    # Auto-detect and connect to available ports
                    logger.info("Auto-detecting Jack network connections...")
                    # Run command to list available ports
                    result = subprocess.run(['jack_lsp'], capture_output=True, text=True)
                    ports = result.stdout.strip().split('\n')
                    
                    # Print all available ports for debugging
                    logger.info(f"Available Jack ports: {ports}")
                    
                    # First try to find controller ports for routing (prioritize these)
                    controller_ports = [p for p in ports if 'controller' in p.lower() and ('in' in p.lower() or 'input' in p.lower())]
                    
                    # Specifically look for the controller's input ports
                    caelus_input_ports = [p for p in ports if 'controller:input' in p.lower()]
                    
                    # System playback as fallback for local use
                    system_ports = [p for p in ports if 'system:playback' in p.lower()]
                    
                    # Also look for netjack ports
                    netjack_ports = [p for p in ports if ('net' in p.lower() or 'jack' in p.lower()) and ('in' in p.lower() or 'input' in p.lower())]
                    
                    # Any input ports as fallback
                    input_ports = [p for p in ports if 'input' in p or 'in_' in p]
                    
                    # Log all detected port categories for debugging
                    logger.info(f"Controller ports: {controller_ports}")
                    logger.info(f"Caelus input ports: {caelus_input_ports}")
                    logger.info(f"System ports: {system_ports}")
                    logger.info(f"NetJack ports: {netjack_ports}")
                    logger.info(f"Input ports: {input_ports}")
                    
                    # Prioritize Caelus controller's input ports for best routing
                    if caelus_input_ports:
                        # Explicitly connect our output to controller's input ports
                        if len(caelus_input_ports) >= 2:
                            # Stereo connection
                            left_port = caelus_input_ports[0]
                            right_port = caelus_input_ports[1]
                            subprocess.run(['jack_connect', f'{jack_client_name}:output_left', left_port])
                            subprocess.run(['jack_connect', f'{jack_client_name}:output_right', right_port])
                            logger.info(f"Connected to Caelus controller inputs: {left_port}, {right_port}")
                        else:
                            # Mono connection (both channels to the same port)
                            port = caelus_input_ports[0]
                            subprocess.run(['jack_connect', f'{jack_client_name}:output_left', port])
                            subprocess.run(['jack_connect', f'{jack_client_name}:output_right', port])
                            logger.info(f"Connected both channels to Caelus controller input: {port}")
                    
                    # Next priority: any controller ports
                    elif controller_ports:
                        for port in controller_ports[:2]:  # Up to 2 ports
                            subprocess.run(['jack_connect', f'{jack_client_name}:output_left', port])
                            subprocess.run(['jack_connect', f'{jack_client_name}:output_right', port])
                            logger.info(f"Connected to controller port: {port}")
                            
                    # For local audio testing, connect to system playback
                    elif self.local_audio and system_ports:
                        # Connect to system output ports
                        for i, port in enumerate(system_ports[:2]):  # Up to 2 ports (stereo)
                            out_port = "output_left" if i == 0 else "output_right"
                            subprocess.run(['jack_connect', f'{jack_client_name}:{out_port}', port])
                            logger.info(f"Connected {out_port} to system output: {port}")
                            
                    # For netjack routing
                    elif netjack_ports:
                        for port in netjack_ports[:2]:  # Up to 2 ports
                            subprocess.run(['jack_connect', f'{jack_client_name}:output_left', port])
                            subprocess.run(['jack_connect', f'{jack_client_name}:output_right', port])
                            logger.info(f"Connected to netjack port: {port}")
                            
                    # Fallback to any input port
                    elif input_ports:
                        for port in input_ports[:2]:  # Up to 2 ports
                            subprocess.run(['jack_connect', f'{jack_client_name}:output_left', port])
                            subprocess.run(['jack_connect', f'{jack_client_name}:output_right', port])
                            logger.info(f"Connected to input port: {port}")
                            
                    # Direct connection to system playback as last resort
                    else:
                        # Try direct connection to system:playback
                        try:
                            subprocess.run(['jack_connect', f'{jack_client_name}:output_left', 'system:playback_1'])
                            subprocess.run(['jack_connect', f'{jack_client_name}:output_right', 'system:playback_2'])
                            logger.info("Connected directly to system playback ports")
                        except Exception as connect_error:
                            logger.warning(f"Failed to connect to system playback: {connect_error}")
                            logger.warning("No suitable output ports found. Audio will be generated but not heard.")
            except Exception as e:
                logger.error(f"Error setting up Jack connections: {e}", exc_info=True)
                
            # Log active status
            logger.info(f"Jack client active with {len(self.active_notes)} notes")
            
            # Keep thread alive until shutdown
            while self.running:
                # Log occasionally
                if random.random() < 0.001:  # Very rarely to avoid log spam
                    if hasattr(self, 'active_notes') and self.active_notes:
                        logger.info(f"Playing {len(self.active_notes)} notes via Jack")
                time.sleep(1)
            
            # Deactivate and close client
            client.deactivate()
            client.close()
            logger.info("Jack client closed")
        
        except Exception as e:
            logger.error(f"Error in JACK thread: {e}")
            # Use network-only mode as fallback
            self._network_audio_engine()
            
        logger.info("Audio synthesis thread stopped")
    
    def _network_audio_engine(self):
        """Network-only audio engine for workers without a local JACK server.
        
        This method creates a synthetic audio engine that:
        1. Generates audio samples in memory
        2. Applies the same gain management and limiting as the JACK version
        3. Prepares audio for streaming to the controller via network
        """
        logger.info("Starting network-only audio engine")
        
        # Audio parameters
        sample_rate = self.sample_rate
        buffer_size = 1024  # Buffer size for processing
        
        # Phase tracking for all notes (for continuous waveforms)
        phase = {}  # note -> current phase
        
        # Process audio in a loop
        while self.running:
            try:
                # Get a snapshot of active notes to avoid mid-callback changes
                current_active_notes = {}
                if hasattr(self, 'active_notes'):
                    current_active_notes = dict(self.active_notes)
                
                # Create silent buffer
                mixed_buffer = np.zeros(buffer_size, dtype=np.float32)
                
                # Only process if we have active notes
                if current_active_notes:
                    # Count active notes for gain scaling
                    active_note_count = len(current_active_notes)
                    
                    # Calculate per-note gain using square-root scaling for perceptual balance
                    # VERY conservative settings to prevent clipping completely
                    if active_note_count > 1:
                        # Use square-root scaling for balanced polyphony, but with more conservative gain
                        note_gain = 0.4 / np.sqrt(active_note_count)
                    else:
                        note_gain = 0.4  # Even single notes should be quieter to prevent clipping
                    
                    # Mix in all active notes with phase continuity
                    for note, (freq, amp) in current_active_notes.items():
                        # Ensure phase is initialized for this note
                        if note not in phase:
                            phase[note] = 0.0
                        
                        # Create continuous-phase oscillator
                        # Calculate phase increment per sample
                        phase_increment = 2 * np.pi * freq / sample_rate
                        
                        # Generate sine wave samples with current amplitude
                        note_buffer = np.zeros(buffer_size, dtype=np.float32)
                        for i in range(buffer_size):
                            note_buffer[i] = amp * np.sin(phase[note])
                            phase[note] += phase_increment
                            # Keep phase in sensible range to prevent floating point errors
                            while phase[note] >= 2 * np.pi:
                                phase[note] -= 2 * np.pi
                        
                        # Apply the calculated gain and mix into the buffer
                        mixed_buffer += note_buffer * note_gain
                    
                    # Clean up phases for notes that are no longer active
                    for note_id in list(phase.keys()):
                        if note_id not in current_active_notes:
                            del phase[note_id]
                
                # Strict limiter to absolutely prevent clipping
                # Apply a more aggressive limiter to ensure no clipping at the worker level
                max_amp = np.max(np.abs(mixed_buffer))
                
                # Two-stage limiting for better audio quality
                # First stage: gentle threshold
                if max_amp > 0.5:
                    # Apply soft knee limiting for a smoother sound
                    target_amp = 0.5
                    gain = target_amp / max_amp
                    mixed_buffer *= gain
                
                # Second stage: safety hard limit at 0.7 to absolutely prevent clipping
                # This is redundant but provides an additional safety net
                max_amp = np.max(np.abs(mixed_buffer))
                if max_amp > 0.7:
                    gain = 0.7 / max_amp
                    mixed_buffer *= gain
                
                # Now mixed_buffer contains the prepared audio that would normally go to JACK
                # In a distributed environment, this would be sent over the network to the controller
                
                # For now, we'll just simulate a controller client
                # In a real implementation, this would send audio data over the network
                # This is where you would add code to send audio to the controller
                
                # Sleep a bit to avoid excessive CPU usage
                # This sleep duration simulates the timing of audio generation
                # In a real JACK setup, this timing is managed by the JACK callback
                time.sleep(buffer_size / sample_rate)
                
            except Exception as e:
                logger.error(f"Error in network audio engine: {e}")
                time.sleep(0.1)  # Short sleep on error
        
        logger.info("Network audio engine stopped")
    
    def _pyaudio_fallback(self):
        """Local audio playback using PyAudio when requested.
        
        Only used when local_audio=True is specified explicitly.
        """
        try:
            # Initialize PyAudio for direct audio output
            import pyaudio
            
            # Audio parameters
            sample_rate = self.sample_rate
            buffer_size = 1024  # Small buffer size for low latency
            
            # Create PyAudio instance
            pa = pyaudio.PyAudio()
            
            # Create stream for real-time audio output
            stream = pa.open(
                format=pyaudio.paFloat32,
                channels=1,
                rate=int(sample_rate),
                output=True,
                frames_per_buffer=buffer_size
            )
            logger.info(f"Created PyAudio output stream at {sample_rate} Hz")
            
            # Main audio loop
            while self.running:
                try:
                    # Generate audio buffer with current active notes
                    # Mix all active notes into a single buffer
                    if hasattr(self, 'active_notes') and self.active_notes:
                        # Create silent buffer
                        mixed_buffer = np.zeros(buffer_size, dtype=np.float32)
                        
                        # Mix in all active notes
                        for note, (freq, amp) in self.active_notes.items():
                            # Generate simple sine wave
                            t = np.linspace(0, buffer_size/sample_rate, buffer_size, False)
                            note_buffer = amp * np.sin(2 * np.pi * freq * t)
                            
                            # Mix by adding (with gain reduction to prevent clipping)
                            mixed_buffer += note_buffer * 0.3
                    else:
                        # No active notes - send silence
                        mixed_buffer = np.zeros(buffer_size, dtype=np.float32)
                    
                    # Limit amplitude to prevent clipping
                    if np.max(np.abs(mixed_buffer)) > 1.0:
                        mixed_buffer = mixed_buffer / np.max(np.abs(mixed_buffer))
                    
                    # Write directly to audio output
                    stream.write(mixed_buffer.tobytes())
                    
                except Exception as e:
                    logger.error(f"Error in PyAudio generation: {e}")
                    time.sleep(0.1)  # Short sleep on error
            
            # Clean up
            stream.stop_stream()
            stream.close()
            pa.terminate()
            logger.info("Closed PyAudio stream")
                
        except Exception as e:
            logger.error(f"Error in PyAudio fallback: {e}")
            logger.error("No audio output available")
    
    def stop(self):
        """Stop the worker."""
        try:
            # Stop all threads
            self.running = False
            
            if self.render_thread:
                self.render_thread.join(timeout=2.0)
                self.render_thread = None
                
            if hasattr(self, 'audio_thread') and self.audio_thread:
                self.audio_thread.join(timeout=2.0)
                self.audio_thread = None
            
            # Stop OSC server
            self.osc_server.stop()
            
            # Close RTP sender
            self.rtp_sender.close()
            
            # Close socket connection if open
            if hasattr(self, 'stream_socket') and self.stream_socket:
                try:
                    self.stream_socket.close()
                    self.stream_socket = None
                    logger.info("Closed direct audio socket connection")
                except Exception as e:
                    logger.error(f"Error closing socket connection: {e}")
            
            # Clean up audio server if local audio was enabled
            if self.local_audio and hasattr(self, 'audio_server'):
                # Stop any remaining active sounds
                if hasattr(self, 'active_sounds'):
                    for note, sound in list(self.active_sounds.items()):
                        try:
                            sound.stop()
                        except Exception as e:
                            logger.error(f"Error stopping sound for note {note}: {e}")
                    self.active_sounds.clear()
                
                # Shut down the audio server
                try:
                    self.audio_server.stop()
                    self.audio_server.shutdown()
                    logger.info("Local audio server shut down")
                except Exception as e:
                    logger.error(f"Error shutting down audio server: {e}")
            
            logger.info("Worker stopped")
        except Exception as e:
            logger.error(f"Error stopping worker: {e}")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Caelus K8s Worker")
    parser.add_argument("--ip", default="0.0.0.0", help="IP to listen on for OSC messages")
    parser.add_argument("--port", type=int, default=9000, help="Port to listen on for OSC messages")
    parser.add_argument("--sr", type=int, default=44100, help="Audio sample rate")
    parser.add_argument("--polyphony", type=int, default=8, help="Maximum polyphony")
    parser.add_argument("--local-audio", action="store_true", help="Enable local audio output")
    parser.add_argument("--use-pyo", action="store_true", help="Use Pyo for local audio (legacy mode)")
    parser.add_argument("--jack-client-name", default="caelus_worker", help="Name to use for Jack client")
    parser.add_argument("--jack-connect-to", help="Jack port to connect to (optional, auto-detected if not specified)")
    parser.add_argument("--controller-ip", default="127.0.0.1", help="IP address of the controller to register with")
    parser.add_argument("--controller-port", type=int, default=8000, help="OSC port of the controller")
    
    args = parser.parse_args()
    
    # Create worker with updated parameters
    worker = CaelusWorker(
        osc_ip=args.ip, 
        osc_port=args.port, 
        sample_rate=args.sr, 
        max_polyphony=args.polyphony, 
        local_audio=args.local_audio,
        use_pyo=args.use_pyo,
        jack_client_name=args.jack_client_name,
        jack_connect_to=args.jack_connect_to
    )
    worker.start(args.controller_ip, args.controller_port)
    
    try:
        # Keep the main thread alive
        print("Worker running. Press Ctrl+C to exit.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        worker.stop()
    except Exception as e:
        logger.error(f"Unhandled exception in worker main: {e}")
        worker.stop()

if __name__ == "__main__":
    main()
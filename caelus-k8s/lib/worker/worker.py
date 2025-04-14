#!/usr/bin/env python3
"""
Worker module for Caelus K8s.
"""

import logging
import argparse
import time
import threading
import numpy as np
from pythonosc import dispatcher

from lib.common.osc import OSCServer, NOTE_ON, NOTE_OFF, WORKER_READY, WORKER_STATUS
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
    
    def __init__(self, osc_ip="0.0.0.0", osc_port=9000, sample_rate=44100, max_polyphony=8, local_audio=False):
        """Initialize the worker.
        
        Args:
            osc_ip (str): IP address to listen on for OSC
            osc_port (int): Port to listen on for OSC
            sample_rate (int): Audio sample rate
            max_polyphony (int): Maximum number of simultaneous notes
            local_audio (bool): If True, play audio locally instead of streaming
        """
        self.osc_ip = osc_ip
        self.osc_port = osc_port
        self.sample_rate = sample_rate
        self.max_polyphony = max_polyphony
        self.local_audio = local_audio
        
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
            
            logger.info(f"Note on: {note}, velocity: {velocity}, RTP port: {rtp_port}")
            
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
                
                # Set up RTP stream to controller if needed
                self.rtp_sender.setup(controller_ip, rtp_port)
                
                # First, ensure any ongoing streaming for THIS NOTE is stopped
                # This is critical - only stop streaming for this specific note!
                self.rtp_sender.stop_streaming(note)
                logger.info(f"Stopped streaming specifically for note {note}")
                
                # Then, if there's a release buffer, stream it without starting a thread
                # Use direct streaming for release buffer to ensure it's sent immediately
                if release_buffer is not None:
                    logger.info(f"Streaming release buffer for note {note}")
                    result = self.rtp_sender.stream_buffer(release_buffer)
                    logger.info(f"Result of streaming release buffer: {result}")
                else:
                    logger.warning(f"No release buffer generated for note {note}")
                
                # Remove from active notes
                del self.active_notes[note]
                logger.info(f"Removed note {note} from active_notes dict (now: {list(self.active_notes.keys())})")
            else:
                logger.warning(f"Received note_off for inactive note: {note}")
        except Exception as e:
            logger.error(f"Error in _handle_note_off: {e}")
    
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
                    
                    # Generate audio - use shorter buffer for sustained note to reduce load
                    duration = 0.5  # 0.5 second of audio (reduced from 1.0)
                    frequency = self.oscillator.note_to_freq(note)
                    amplitude = velocity / 127.0
                    
                    # Generate continuous tone - sine wave audio
                    t = np.linspace(0, duration, int(self.sample_rate * duration), False)
                    audio_buffer = amplitude * np.sin(2 * np.pi * frequency * t)
                    
                    # If local audio is enabled, play it directly
                    if self.local_audio:
                        from pyo import Sine
                        # Create a sine oscillator and play it
                        sine = Sine(freq=float(frequency), mul=amplitude).out()
                        # Store in a dictionary to keep track of active sounds
                        if not hasattr(self, 'active_sounds'):
                            self.active_sounds = {}
                        self.active_sounds[note] = sine
                        logger.info(f"Playing note {note} locally with frequency {frequency:.2f} Hz")
                    
                    # Also stream via RTP as normal
                    # Stream audio in chunks for better playback
                    # Using smaller chunks and longer intervals to prevent controller buffer overflow
                    chunk_size = 512  # Smaller chunks
                    chunk_interval = 0.05  # 50ms between chunks, for ~20 packets per second
                    
                    # Use chunked streaming for better playback
                    # Pass the note number so we can track which note is being played
                    self.rtp_sender.stream_buffer_chunked(
                        audio_buffer, 
                        chunk_size=chunk_size,
                        chunk_interval=chunk_interval,
                        note=note  # Pass the note ID so we can stop specific notes later
                    )
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
            
            # Send WORKER_READY message with our IP, port, and capacity
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
            
            controller_client.client.send_message(WORKER_READY, [my_ip, self.osc_port, self.max_polyphony])
            logger.info(f"Registered with controller at {controller_ip}:{controller_port}")
            
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
        
        logger.info("Worker started")
    
    def stop(self):
        """Stop the worker."""
        try:
            # Stop render thread
            self.running = False
            if self.render_thread:
                self.render_thread.join(timeout=2.0)
                self.render_thread = None
            
            # Stop OSC server
            self.osc_server.stop()
            
            # Close RTP sender
            self.rtp_sender.close()
            
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
    parser.add_argument("--controller-ip", default="127.0.0.1", help="IP address of the controller to register with")
    parser.add_argument("--controller-port", type=int, default=8000, help="OSC port of the controller")
    
    args = parser.parse_args()
    
    worker = CaelusWorker(args.ip, args.port, args.sr, args.polyphony, args.local_audio)
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
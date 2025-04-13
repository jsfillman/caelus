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
    
    def __init__(self, osc_ip="0.0.0.0", osc_port=9000, sample_rate=44100, max_polyphony=8):
        """Initialize the worker.
        
        Args:
            osc_ip (str): IP address to listen on for OSC
            osc_port (int): Port to listen on for OSC
            sample_rate (int): Audio sample rate
            max_polyphony (int): Maximum number of simultaneous notes
        """
        self.osc_ip = osc_ip
        self.osc_port = osc_port
        self.sample_rate = sample_rate
        self.max_polyphony = max_polyphony
        
        # Create oscillator and RTP sender
        self.oscillator = SineOscillator(sr=sample_rate)
        self.rtp_sender = RTPSender(sr=sample_rate)
        
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
            
            # Store active note
            self.active_notes[note] = (self.oscillator.note_to_freq(note), velocity/127.0)
            
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
                
                # Generate release buffer
                release_buffer = self.oscillator.stop_note(note)
                
                # Set up RTP stream to controller if needed
                self.rtp_sender.setup(controller_ip, rtp_port)
                
                # If there's a release buffer, stream it
                if release_buffer is not None:
                    self.rtp_sender.stream_buffer(release_buffer)
                
                # Remove from active notes
                del self.active_notes[note]
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
                    
                    # Generate audio - use longer buffer for sustained note
                    duration = 1.0  # 1 second of audio
                    frequency = self.oscillator.note_to_freq(note)
                    amplitude = velocity / 127.0
                    
                    # Generate continuous tone - 1 second of sine wave audio
                    t = np.linspace(0, duration, int(self.sample_rate * duration), False)
                    audio_buffer = amplitude * np.sin(2 * np.pi * frequency * t)
                    
                    # Stream audio in chunks for better playback
                    chunk_size = 1024
                    chunk_interval = 0.02  # 20ms between chunks, for ~50 packets per second
                    
                    # Use chunked streaming for better playback
                    self.rtp_sender.stream_buffer_chunked(
                        audio_buffer, 
                        chunk_size=chunk_size,
                        chunk_interval=chunk_interval
                    )
                else:
                    # Sleep a bit if no work to do
                    time.sleep(0.01)
                
            except Exception as e:
                logger.error(f"Error in render thread: {e}")
        
        logger.info("Audio render thread stopped")
    
    def start(self):
        """Start the worker."""
        # Start OSC server
        self.osc_server.start()
        
        # Start render thread
        self.running = True
        self.render_thread = threading.Thread(target=self._render_thread_func)
        self.render_thread.daemon = True
        self.render_thread.start()
        
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
    
    args = parser.parse_args()
    
    worker = CaelusWorker(args.ip, args.port, args.sr, args.polyphony)
    worker.start()
    
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
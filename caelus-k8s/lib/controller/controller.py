#!/usr/bin/env python3
"""
Controller module for Caelus K8s.
"""

import logging
import argparse
import time
import random
import threading
from mido import Message

from lib.common.osc import OSCClient, OSCServer, WORKER_STATUS, WORKER_READY
from lib.controller.midi import MIDIInputHandler
from lib.controller.rtp import RTPReceiver

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WorkerConfig:
    """Configuration for a worker node."""
    
    def __init__(self, ip, osc_port):
        """Initialize worker configuration.
        
        Args:
            ip (str): IP address of the worker
            osc_port (int): OSC port of the worker
        """
        self.ip = ip
        self.osc_port = osc_port
        self.osc_client = OSCClient(ip, osc_port)
        self.active_notes = set()  # Set of currently playing notes
        self.note_capacity = 8     # Maximum notes this worker can play
        self.last_ping = 0         # Last time we received a status update
        self.status = "unknown"    # Current status
        
        logger.info(f"Worker configuration created for {ip}:{osc_port}")

class CaelusController:
    """Caelus K8s controller that routes MIDI to workers via OSC."""
    
    def __init__(self, rtp_port=5000):
        """Initialize the controller.
        
        Args:
            rtp_port (int): Port to listen on for RTP
        """
        self.rtp_port = rtp_port
        
        # Create worker registry
        self.workers = {}  # ip -> WorkerConfig
        self.workers_lock = threading.Lock()
        
        # Create OSC server to receive worker status updates
        self.dispatcher = self._create_dispatcher()
        self.osc_server = OSCServer("0.0.0.0", 8000, self.dispatcher)
        
        # Create RTP receiver to get audio from workers
        self.rtp_receiver = RTPReceiver()
        
        # Create MIDI input handler
        self.midi_handler = MIDIInputHandler()
        self.midi_handler.set_callback(self._handle_midi_message)
        
        # Set of all active notes across all workers
        self.active_notes = {}  # note -> worker_ip
        
        logger.info(f"Controller initialized")
    
    def _create_dispatcher(self):
        """Create OSC dispatcher with custom handlers.
        
        Returns:
            dispatcher: OSC dispatcher
        """
        from pythonosc import dispatcher
        disp = dispatcher.Dispatcher()
        disp.map(WORKER_READY, self._handle_worker_ready)
        disp.map(WORKER_STATUS, self._handle_worker_status)
        return disp
    
    def _handle_worker_ready(self, address, *args):
        """Handle worker ready message.
        
        Args:
            address (str): OSC address
            *args: OSC arguments (worker_ip, osc_port, capacity)
        """
        try:
            if len(args) < 3:
                logger.error(f"Not enough arguments for worker_ready: {args}")
                return
                
            worker_ip = args[0]
            osc_port = args[1]
            capacity = args[2]
            
            with self.workers_lock:
                if worker_ip in self.workers:
                    # Update existing worker
                    self.workers[worker_ip].osc_port = osc_port
                    self.workers[worker_ip].note_capacity = capacity
                    self.workers[worker_ip].last_ping = time.time()
                    self.workers[worker_ip].status = "ready"
                    logger.info(f"Worker updated: {worker_ip}:{osc_port}, capacity: {capacity}")
                else:
                    # Add new worker
                    worker = WorkerConfig(worker_ip, osc_port)
                    worker.note_capacity = capacity
                    worker.last_ping = time.time()
                    worker.status = "ready"
                    self.workers[worker_ip] = worker
                    logger.info(f"New worker added: {worker_ip}:{osc_port}, capacity: {capacity}")
        except Exception as e:
            logger.error(f"Error in _handle_worker_ready: {e}")
    
    def _handle_worker_status(self, address, *args):
        """Handle worker status message.
        
        Args:
            address (str): OSC address
            *args: OSC arguments (worker_ip, active_notes, capacity)
        """
        try:
            if len(args) < 3:
                logger.error(f"Not enough arguments for worker_status: {args}")
                return
                
            worker_ip = args[0]
            active_notes = args[1]
            capacity = args[2]
            
            with self.workers_lock:
                if worker_ip in self.workers:
                    # Update worker status
                    self.workers[worker_ip].last_ping = time.time()
                    self.workers[worker_ip].note_capacity = capacity
                    logger.debug(f"Worker status updated: {worker_ip}, active_notes: {active_notes}/{capacity}")
                else:
                    # This should not happen, but add the worker if it doesn't exist
                    logger.warning(f"Received status from unknown worker: {worker_ip}")
                    worker = WorkerConfig(worker_ip, 9000)  # Default OSC port
                    worker.note_capacity = capacity
                    worker.last_ping = time.time()
                    worker.status = "unknown"
                    self.workers[worker_ip] = worker
        except Exception as e:
            logger.error(f"Error in _handle_worker_status: {e}")
    
    def _handle_midi_message(self, message):
        """Handle MIDI messages.
        
        Args:
            message (mido.Message): MIDI message
        """
        if message.type == 'note_on' and message.velocity > 0:
            self._handle_note_on(message.note, message.velocity)
        elif message.type == 'note_off' or (message.type == 'note_on' and message.velocity == 0):
            self._handle_note_off(message.note)
    
    def _find_worker_for_note(self):
        """Find a worker to play a new note.
        
        Returns:
            str: IP address of the selected worker, or None if no worker is available
        """
        with self.workers_lock:
            # If no workers, return None
            if not self.workers:
                return None
            
            # Find workers with available capacity
            available_workers = [ip for ip, worker in self.workers.items()
                               if len(worker.active_notes) < worker.note_capacity]
            
            if not available_workers:
                # No workers with available capacity
                return None
            
            # Choose the worker with the least active notes
            return min(available_workers, 
                      key=lambda ip: len(self.workers[ip].active_notes))
    
    def _handle_note_on(self, note, velocity):
        """Handle note on MIDI message.
        
        Args:
            note (int): MIDI note number
            velocity (int): MIDI velocity
        """
        logger.info(f"Note on: {note}, velocity: {velocity}")
        
        # Check if note is already playing
        if note in self.active_notes:
            # Send note off to the current worker first
            worker_ip = self.active_notes[note]
            if worker_ip in self.workers:
                self.workers[worker_ip].osc_client.send_note_off(note)
                self.workers[worker_ip].active_notes.remove(note)
        
        # Find a worker to play the note
        worker_ip = self._find_worker_for_note()
        if worker_ip is None:
            logger.warning(f"No available workers for note {note}")
            return
        
        # Add note to active notes
        self.active_notes[note] = worker_ip
        self.workers[worker_ip].active_notes.add(note)
        
        # Send note on OSC message to worker
        self.workers[worker_ip].osc_client.send_note_on(note, velocity, self.rtp_port)
        logger.info(f"Assigned note {note} to worker {worker_ip}")
    
    def _handle_note_off(self, note):
        """Handle note off MIDI message.
        
        Args:
            note (int): MIDI note number
        """
        logger.info(f"Note off: {note}")
        
        # Check if note is playing
        if note in self.active_notes:
            worker_ip = self.active_notes[note]
            
            # Send note off OSC message to worker
            if worker_ip in self.workers:
                self.workers[worker_ip].osc_client.send_note_off(note)
                self.workers[worker_ip].active_notes.remove(note)
            
            # Remove note from active notes
            del self.active_notes[note]
        else:
            logger.warning(f"Note off for inactive note: {note}")
    
    def add_worker(self, ip, osc_port):
        """Add a worker to the controller.
        
        Args:
            ip (str): IP address of the worker
            osc_port (int): OSC port of the worker
        """
        with self.workers_lock:
            if ip in self.workers:
                logger.warning(f"Worker {ip} already exists, updating port to {osc_port}")
                self.workers[ip].osc_port = osc_port
                self.workers[ip].osc_client = OSCClient(ip, osc_port)
            else:
                worker = WorkerConfig(ip, osc_port)
                self.workers[ip] = worker
                logger.info(f"Added worker: {ip}:{osc_port}")
    
    def start(self):
        """Start the controller."""
        # Set up RTP receiver
        if not self.rtp_receiver.setup(self.rtp_port):
            logger.error("Failed to set up RTP receiver")
            return False
        
        # Start OSC server
        self.osc_server.start()
        
        # Try to open a MIDI port
        if not self.midi_handler.open_port():
            # If no physical MIDI ports available, open a virtual port
            logger.warning("No physical MIDI ports available, opening virtual port")
            if not self.midi_handler.open_virtual_port():
                logger.error("Failed to open MIDI port")
                return False
        
        logger.info("Controller started")
        return True
    
    def stop(self):
        """Stop the controller."""
        # Close MIDI port
        self.midi_handler.close_port()
        
        # Stop RTP receiver
        self.rtp_receiver.stop()
        
        # Stop OSC server
        self.osc_server.stop()
        
        # Send note off for any active notes
        for note, worker_ip in list(self.active_notes.items()):
            if worker_ip in self.workers:
                self.workers[worker_ip].osc_client.send_note_off(note)
        
        logger.info("Controller stopped")
    
    def test_notes(self):
        """Send test notes."""
        # C major chord
        notes = [60, 64, 67]  # C, E, G
        
        for note in notes:
            # Note on
            self._handle_note_on(note, 100)
            
            # Wait for a bit
            time.sleep(1.0)
            
            # Note off
            self._handle_note_off(note)
            
            # Wait between notes
            time.sleep(0.5)
        
        # C major chord (all at once)
        for note in notes:
            self._handle_note_on(note, 100)
        
        # Wait for the chord to play
        time.sleep(2.0)
        
        # Note off for all notes
        for note in notes:
            self._handle_note_off(note)
        
        logger.info("Test notes completed")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Caelus K8s Controller")
    parser.add_argument("--rtp-port", type=int, default=5000, help="Port to listen on for RTP")
    parser.add_argument("--worker-ip", default=None, help="IP address of the worker")
    parser.add_argument("--worker-port", type=int, default=9000, help="OSC port of the worker")
    parser.add_argument("--test", action="store_true", help="Send test notes")
    
    args = parser.parse_args()
    
    controller = CaelusController(args.rtp_port)
    
    # Add worker if specified
    if args.worker_ip:
        controller.add_worker(args.worker_ip, args.worker_port)
    
    if controller.start():
        try:
            if args.test:
                controller.test_notes()
            else:
                # Keep the main thread alive
                print("Controller running. Press Ctrl+C to exit.")
                while True:
                    time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            controller.stop()

if __name__ == "__main__":
    main()
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
    
    def __init__(self, ip, osc_port, note_capacity=1):
        """Initialize worker configuration.
        
        Args:
            ip (str): IP address of the worker
            osc_port (int): OSC port of the worker
            note_capacity (int): Maximum number of notes this worker can play simultaneously
        """
        self.ip = ip
        self.osc_port = osc_port
        self.osc_client = OSCClient(ip, osc_port)
        self.active_notes = set()  # Set of currently playing notes
        self.note_capacity = note_capacity  # Default to 1 note (monophonic)
        self.last_ping = time.time()  # Last time we received a status update
        self.status = "unknown"       # Current status
        
        # Track some basic stats
        self.notes_played = 0       # Total notes played
        self.notes_stolen = 0       # Number of notes stolen from this worker
        
        logger.info(f"Worker configuration created for {ip}:{osc_port} with capacity {note_capacity}")

class CaelusController:
    """Caelus K8s controller that routes MIDI to workers via OSC."""
    
    def __init__(self, rtp_port=5000, offline_mode=False, sr=44100, 
                 jack_client_name="caelus_controller", use_jack=True):
        """Initialize the controller.
        
        Args:
            rtp_port (int): Port to listen on for RTP/socket audio
            offline_mode (bool): If True, don't try to use audio output
            sr (int): Sample rate for audio processing
            jack_client_name (str): Name for Jack client
            use_jack (bool): Whether to use Jack for audio I/O
        """
        self.offline_mode = offline_mode
        self.rtp_port = rtp_port
        self.sample_rate = sr  # Store sample rate to ensure consistency
        self.jack_client_name = jack_client_name
        self.use_jack = use_jack
        
        # Create worker registry
        self.workers = {}  # ip -> WorkerConfig
        self.workers_lock = threading.Lock()
        
        # Create OSC server to receive worker status updates
        self.dispatcher = self._create_dispatcher()
        self.osc_server = OSCServer("0.0.0.0", 8000, self.dispatcher)
        
        # Create RTP receiver to get audio from workers
        # Pass offline_mode to constructor later when setting up
        
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
            # Print the raw arguments to debug
            logger.info(f"Worker ready message received with args: {args}")
            
            if len(args) < 3:
                logger.error(f"Not enough arguments for worker_ready: {args}")
                return
                
            worker_ip = args[0]
            osc_port = int(args[1])  # Make sure port is an integer
            capacity = int(args[2])  # Make sure capacity is an integer
            
            # Print for debugging
            logger.info(f"Parsed worker info: IP={worker_ip}, Port={osc_port}, Capacity={capacity}")
            
            # Create a unique worker ID to avoid worker IP collisions 
            # when multiple workers run on the same host
            worker_id = f"{worker_ip}:{osc_port}"
            
            with self.workers_lock:
                if worker_id in self.workers:
                    # Update existing worker
                    self.workers[worker_id].osc_port = osc_port
                    self.workers[worker_id].note_capacity = capacity
                    self.workers[worker_id].last_ping = time.time()
                    self.workers[worker_id].status = "ready"
                    logger.info(f"Worker updated: {worker_id}, capacity: {capacity}")
                else:
                    # Add new worker
                    worker = WorkerConfig(worker_ip, osc_port, capacity)
                    worker.last_ping = time.time()
                    worker.status = "ready"
                    self.workers[worker_id] = worker
                    logger.info(f"New worker added: {worker_id}, capacity: {capacity}")
                    
                # Log all currently registered workers for debugging
                worker_info = [f"{id} (capacity: {w.note_capacity}, active_notes: {len(w.active_notes)})" 
                             for id, w in self.workers.items()]
                logger.info(f"Current workers: {worker_info}")
                logger.info(f"Total workers now registered: {len(self.workers)}")
        except Exception as e:
            logger.error(f"Error in _handle_worker_ready: {e}", exc_info=True)
    
    def _handle_worker_status(self, address, *args):
        """Handle worker status message.
        
        Args:
            address (str): OSC address
            *args: OSC arguments (worker_ip, osc_port, active_notes, capacity)
        """
        try:
            if len(args) < 3:
                logger.error(f"Not enough arguments for worker_status: {args}")
                return
                
            worker_ip = args[0]
            # If provided, use osc_port from args, otherwise default to 9000
            osc_port = int(args[1]) if len(args) > 3 else 9000
            active_notes = args[1] if len(args) == 3 else args[2]
            capacity = args[2] if len(args) == 3 else args[3]
            
            # Create worker ID in the same format as _handle_worker_ready
            worker_id = f"{worker_ip}:{osc_port}"
            
            with self.workers_lock:
                if worker_id in self.workers:
                    # Update worker status
                    self.workers[worker_id].last_ping = time.time()
                    self.workers[worker_id].note_capacity = capacity
                    logger.debug(f"Worker status updated: {worker_id}, active_notes: {active_notes}/{capacity}")
                else:
                    # This should not happen, but add the worker if it doesn't exist
                    logger.warning(f"Received status from unknown worker: {worker_id}")
                    worker = WorkerConfig(worker_ip, osc_port)
                    worker.note_capacity = capacity
                    worker.last_ping = time.time()
                    worker.status = "unknown"
                    self.workers[worker_id] = worker
                    
                # Log all registered workers
                logger.info(f"Total workers after status update: {len(self.workers)}")
        except Exception as e:
            logger.error(f"Error in _handle_worker_status: {e}", exc_info=True)
    
    def _handle_midi_message(self, message):
        """Handle MIDI messages.
        
        Args:
            message (mido.Message): MIDI message
        """
        # Debug print to see what messages we're receiving
        logger.info(f"MIDI message received: {message}")
        
        if message.type == 'note_on' and message.velocity > 0:
            self._handle_note_on(message.note, message.velocity)
        elif message.type == 'note_off' or (message.type == 'note_on' and message.velocity == 0):
            self._handle_note_off(message.note)
    
    def _find_worker_for_note(self, note):
        """Find a worker to play a new note, with note stealing if needed.
        
        Args:
            note (int): MIDI note number to be played
            
        Returns:
            tuple: (worker_ip, stolen_note) where:
                - worker_ip: IP address of the selected worker
                - stolen_note: Note that was stolen, or None if no stealing occurred
        """
        with self.workers_lock:
            # Debug: Print all workers and their current state
            logger.info(f"Total workers registered: {len(self.workers)}")
            for ip, worker in self.workers.items():
                logger.info(f"Worker {ip}:{worker.osc_port} has {len(worker.active_notes)}/{worker.note_capacity} notes: {worker.active_notes}")
            
            # If no workers, return None
            if not self.workers:
                logger.warning("No workers available")
                return None, None
            
            # Fix: Ensure we're using the right key for the worker dictionary
            # Make a list of all worker IPs for debugging
            all_worker_ips = list(self.workers.keys())
            logger.info(f"All worker IPs: {all_worker_ips}")
            
            # Step 1: Find workers with available capacity
            available_workers = []
            for ip, worker in self.workers.items():
                # Extra debug info
                logger.info(f"Checking worker {ip} - active notes: {len(worker.active_notes)}, capacity: {worker.note_capacity}")
                if len(worker.active_notes) < worker.note_capacity:
                    available_workers.append(ip)
            
            # Debug
            logger.info(f"Available workers with free capacity: {available_workers}")
            
            if available_workers:
                # We have workers with free capacity
                # Choose the worker with the least active notes for best load balancing
                worker_ip = min(available_workers, key=lambda ip: len(self.workers[ip].active_notes))
                logger.info(f"Selected worker {worker_ip} based on free capacity")
                return worker_ip, None
            
            # Step 2: No workers have free capacity, need to perform note stealing
            # Get all active workers
            active_workers = list(self.workers.keys())
            if not active_workers:
                logger.warning("No active workers found")
                return None, None
                
            # Find oldest note based on the global active_notes
            # This is used to implement "last note priority" - older notes get stolen first
            oldest_time = float('inf')
            oldest_note = None
            oldest_worker = None
            
            # Track note timestamps if not already doing so
            if not hasattr(self, 'note_timestamps'):
                self.note_timestamps = {}  # note -> timestamp
                
            logger.info(f"Active notes for stealing: {self.active_notes}")
            
            # Find the oldest note across all workers
            for active_note, worker_id in self.active_notes.items():
                # Skip if worker no longer exists
                if worker_id not in self.workers:
                    continue
                    
                # Get timestamp, defaulting to now if not recorded
                timestamp = self.note_timestamps.get(active_note, time.time())
                
                # Keep track of the oldest note
                if timestamp < oldest_time:
                    oldest_time = timestamp
                    oldest_note = active_note
                    oldest_worker = worker_id
                    logger.info(f"Found potential note to steal: {active_note} from {worker_id} (timestamp: {timestamp})")
            
            if oldest_note is not None:
                # Return the worker and the note to be stolen
                logger.info(f"Stealing note {oldest_note} from worker {oldest_worker}")
                return oldest_worker, oldest_note
            
            # If we get here, something is wrong (no active notes but no capacity)
            logger.warning("No workers available and no notes to steal")
            return None, None
    
    def _handle_note_on(self, note, velocity):
        """Handle note on MIDI message with note stealing when needed.
        
        Args:
            note (int): MIDI note number
            velocity (int): MIDI velocity
        """
        logger.info(f"Note on: {note}, velocity: {velocity}")
        
        # Ignore velocity 0 (treated as note-off in some MIDI devices)
        if velocity == 0:
            self._handle_note_off(note)
            return
            
        # Check if note is already playing
        if note in self.active_notes:
            # Already playing, stop the previous instance
            self._handle_note_off(note)
        
        # Find a worker to play the note, with possible note stealing
        worker_id, stolen_note = self._find_worker_for_note(note)
        if worker_id is None:
            logger.warning(f"No available workers for note {note}")
            return
        
        # If we need to steal a note, turn off the stolen note first
        if stolen_note is not None:
            logger.info(f"Note stealing: turning off note {stolen_note} to make room for {note}")
            self._handle_note_off(stolen_note)
        
        # Extract IP and port from worker_id
        worker_ip = worker_id.split(':')[0]
        
        # Add note to active notes
        self.active_notes[note] = worker_id
        self.workers[worker_id].active_notes.add(note)
        
        # Track timestamp for note stealing priority
        if not hasattr(self, 'note_timestamps'):
            self.note_timestamps = {}
        self.note_timestamps[note] = time.time()
        
        # Each worker gets one RTP port - the base port
        # This ensures monophonic playback per worker
        worker_port = self.rtp_port
        
        # Send the note message
        self.workers[worker_id].osc_client.send_note_on(note, velocity, worker_port)
        logger.info(f"Assigned note {note} to worker {worker_id} (port {worker_port})")
        
        # Debug after assignment
        logger.info(f"Worker {worker_id} now has {len(self.workers[worker_id].active_notes)} active notes: {self.workers[worker_id].active_notes}")
    
    def _handle_note_off(self, note):
        """Handle note off MIDI message.
        
        Args:
            note (int): MIDI note number
        """
        logger.info(f"Note off: {note}")
        
        # Check if note is playing
        if note in self.active_notes:
            worker_id = self.active_notes[note]
            
            # Send note off OSC message to worker
            if worker_id in self.workers:
                self.workers[worker_id].osc_client.send_note_off(note)
                # Remove note from worker's active notes set
                if note in self.workers[worker_id].active_notes:
                    self.workers[worker_id].active_notes.remove(note)
                    
                logger.info(f"Worker {worker_id} after note-off has {len(self.workers[worker_id].active_notes)} active notes: {self.workers[worker_id].active_notes}")
            else:
                logger.warning(f"Worker {worker_id} not found in workers dictionary")
            
            # Remove note from active notes dictionary
            del self.active_notes[note]
            
            # Remove from timestamps if we're tracking them
            if hasattr(self, 'note_timestamps') and note in self.note_timestamps:
                del self.note_timestamps[note]
            
            # Controller just needs to send note off to worker
            # Let the worker handle the actual note lifecycle and audio generation
            # This is a cleaner separation of concerns
            
            # Log the action for debugging
            logger.info(f"Note-off sent to worker {worker_id} for note {note}")
        else:
            logger.warning(f"Note off for inactive note: {note}")
    
    def add_worker(self, ip, osc_port, note_capacity=1):
        """Add a worker to the controller.
        
        Args:
            ip (str): IP address of the worker
            osc_port (int): OSC port of the worker
            note_capacity (int): Number of simultaneous notes this worker can play
        """
        # Create a unique worker ID
        worker_id = f"{ip}:{osc_port}"
        
        with self.workers_lock:
            if worker_id in self.workers:
                logger.warning(f"Worker {worker_id} already exists, updating configuration")
                self.workers[worker_id].osc_port = osc_port
                self.workers[worker_id].osc_client = OSCClient(ip, osc_port)
                self.workers[worker_id].note_capacity = note_capacity
            else:
                worker = WorkerConfig(ip, osc_port, note_capacity)
                self.workers[worker_id] = worker
                logger.info(f"Added worker: {worker_id} with capacity {note_capacity}")
                
            # Log all workers after adding
            logger.info(f"Total workers after add_worker: {len(self.workers)}")
            worker_info = [f"{id} (capacity: {w.note_capacity})" for id, w in self.workers.items()]
            logger.info(f"Current workers: {worker_info}")
    
    def start(self):
        """Start the controller."""
        # Create and set up RTP/audio receiver
        self.rtp_receiver = RTPReceiver(sr=self.sample_rate, jack_client_name=self.jack_client_name)
        
        # Set up audio receiver
        if self.offline_mode:
            logger.info("Starting in offline mode (no audio output)")
            # Initialize with offline audio mode
            if not self.rtp_receiver.setup(self.rtp_port, offline=True, use_jack=False):
                logger.error("Failed to set up audio receiver in offline mode")
                return False
        else:
            # Try regular audio output with Jack if enabled
            if not self.rtp_receiver.setup(self.rtp_port, offline=False, use_jack=self.use_jack):
                logger.error("Failed to set up audio receiver")
                return False
        
        # Start OSC server
        self.osc_server.start()
        
        # Try to open a MIDI port
        if not self.midi_handler.open_port(interactive=midi_select_flag):
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
        # C major arpeggio
        notes = [60, 64, 67, 72, 76]  # C, E, G, C', E'
        
        # Play ascending arpeggio
        for note in notes:
            # Note on
            self._handle_note_on(note, 100)
            
            # Wait for the note to sound
            time.sleep(0.3)
            
            # Note off
            self._handle_note_off(note)
            
            # Small gap between notes
            time.sleep(0.1)
        
        # Play descending arpeggio
        for note in reversed(notes):
            # Note on
            self._handle_note_on(note, 100)
            
            # Wait for the note to sound
            time.sleep(0.3)
            
            # Note off
            self._handle_note_off(note)
            
            # Small gap between notes
            time.sleep(0.1)
        
        # Play triad chord
        triad = [60, 64, 67]  # C, E, G
        
        # Send notes one at a time with small timing differences
        for i, note in enumerate(triad):
            self._handle_note_on(note, 100)
            time.sleep(0.05)  # Small delay between notes
        
        # Let the chord ring
        time.sleep(1.0)
        
        # Note off for all notes in reverse order
        for note in reversed(triad):
            self._handle_note_off(note)
            time.sleep(0.05)
        
        logger.info("Test notes completed")
    
    def test_polyphony(self):
        """Test polyphonic capabilities with note stealing.
        
        This test specifically exercises multi-worker polyphony and note stealing.
        """
        logger.info("Starting polyphony test")
        
        # Count workers and their total capacity
        worker_count = len(self.workers)
        total_capacity = sum(worker.note_capacity for worker in self.workers.values())
        
        # Log details about each configured worker
        for worker_id, worker in self.workers.items():
            logger.info(f"Worker {worker_id} configured with capacity: {worker.note_capacity}")
        
        logger.info(f"Testing with {worker_count} workers, total capacity: {total_capacity} notes")
        
        # C major scale notes
        scale = [60, 62, 64, 65, 67, 69, 71, 72]  # C, D, E, F, G, A, B, C'
        
        # Test 1: Sequential notes up to capacity
        logger.info("Test 1: Play sequential notes up to capacity")
        active_notes = []
        
        # Play notes up to capacity
        for i in range(min(total_capacity, len(scale))):
            note = scale[i]
            self._handle_note_on(note, 100)
            active_notes.append(note)
            time.sleep(0.5)  # Let each note sound
            
            # Print current active notes
            logger.info(f"Active notes: {active_notes}")
        
        # Let all notes sound together
        time.sleep(1.0)
        
        # Turn off all notes
        for note in active_notes:
            self._handle_note_off(note)
            time.sleep(0.1)
        
        # Test 2: Note stealing
        if total_capacity < len(scale):
            logger.info("Test 2: Note stealing when exceeding capacity")
            active_notes = []
            
            # Play notes to fill capacity
            for i in range(total_capacity):
                note = scale[i]
                self._handle_note_on(note, 100)
                active_notes.append(note)
                time.sleep(0.5)
                
            # Try to play additional notes beyond capacity (should trigger note stealing)
            for i in range(total_capacity, len(scale)):
                # This should cause note stealing
                logger.info(f"Playing note {scale[i]} beyond capacity (should steal oldest note)")
                self._handle_note_on(scale[i], 100)
                time.sleep(0.5)
            
            # Turn off any remaining notes
            for note in list(self.active_notes.keys()):
                self._handle_note_off(note)
                time.sleep(0.1)
        
        # Test 3: Chord with note stealing
        logger.info("Test 3: Chord with potential note stealing")
        
        # C major chord (more notes than we might have capacity for)
        chord = [60, 64, 67, 72, 76, 79]  # C, E, G, C', E', G'
        
        # Play chord notes all at once
        for note in chord:
            self._handle_note_on(note, 100)
            time.sleep(0.05)  # Very small delay
        
        # Let the chord ring
        time.sleep(1.0)
        
        # Show which notes are actually playing
        logger.info(f"Chord notes playing: {list(self.active_notes.keys())}")
        
        # Turn off all notes
        for note in list(self.active_notes.keys()):
            self._handle_note_off(note)
            time.sleep(0.1)
        
        logger.info("Polyphony test completed")

# Global variable to store command line arguments
midi_select_flag = False

def main():
    """Main entry point."""
    global midi_select_flag
    
    parser = argparse.ArgumentParser(description="Caelus K8s Controller")
    parser.add_argument("--rtp-port", type=int, default=5000, help="Port to listen on for RTP")
    
    # Support for multiple workers
    parser.add_argument("--workers", nargs='+', default=[], 
                        help="List of workers in format ip:port:capacity, e.g. '127.0.0.1:9000:1 127.0.0.1:9001:1'")
    
    # Legacy single worker support
    parser.add_argument("--worker-ip", default=None, help="IP address of a single worker (legacy mode)")
    parser.add_argument("--worker-port", type=int, default=9000, help="OSC port of the worker (legacy mode)")
    parser.add_argument("--worker-capacity", type=int, default=1, help="Note capacity of the worker (legacy mode)")
    
    parser.add_argument("--test", action="store_true", help="Send test notes")
    parser.add_argument("--test-polyphony", action="store_true", help="Test polyphonic capabilities with note stealing")
    parser.add_argument("--offline", action="store_true", help="Run in offline mode (disable audio reception/playback)")
    parser.add_argument("--select-midi", action="store_true", help="Interactively select MIDI input device")
    parser.add_argument("--no-jack", action="store_true", help="Disable Jack audio (use socket mode)")
    parser.add_argument("--jack-client-name", default="caelus_controller", help="Jack client name")
    
    args = parser.parse_args()
    
    # Store MIDI selection flag globally
    midi_select_flag = args.select_midi
    
    # Create controller with appropriate settings
    controller = CaelusController(
        rtp_port=args.rtp_port, 
        offline_mode=args.offline,
        jack_client_name=args.jack_client_name,
        use_jack=not args.no_jack
    )
    
    # Add multiple workers if specified
    for worker_spec in args.workers:
        try:
            # Parse worker specification (ip:port:capacity)
            parts = worker_spec.split(':')
            if len(parts) == 3:
                ip, port, capacity = parts
                controller.add_worker(ip, int(port), int(capacity))
                logger.info(f"Added worker from command line: {ip}:{port} with capacity {capacity}")
            elif len(parts) == 2:
                ip, port = parts
                controller.add_worker(ip, int(port), 1)  # Default capacity 1
                logger.info(f"Added worker from command line: {ip}:{port} with default capacity 1")
            else:
                logger.error(f"Invalid worker specification: {worker_spec}, expected format ip:port:capacity")
        except Exception as e:
            logger.error(f"Error adding worker {worker_spec}: {e}")
    
    # Add legacy single worker if specified
    if args.worker_ip:
        controller.add_worker(args.worker_ip, args.worker_port, args.worker_capacity)
        logger.info(f"Added legacy worker from command line: {args.worker_ip}:{args.worker_port} with capacity {args.worker_capacity}")
        
    # Log total worker count after setup
    logger.info(f"Configured with {len(controller.workers)} workers")
    
    if controller.start():
        try:
            if args.test:
                controller.test_notes()
            elif args.test_polyphony:
                controller.test_polyphony()
            else:
                # Print a summary of workers and their capacities
                print("\nCaelus Controller Running")
                print("-------------------------")
                for ip, worker in controller.workers.items():
                    print(f"Worker: {ip}:{worker.osc_port} - Capacity: {worker.note_capacity} notes")
                total_capacity = sum(worker.note_capacity for worker in controller.workers.values())
                print(f"Total polyphony: {total_capacity} notes\n")
                
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
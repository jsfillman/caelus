import mido
import threading
import time
from pythonosc import udp_client
from pythonosc import osc_bundle_builder
from pythonosc import osc_message_builder

# --- OSC Setup ---
OSC_IP = "127.0.0.1"
OSC_PORT = 9000  # Changed to send to router port instead of synth port
ROUTER_NAME = "router"  # Name of the router endpoint
osc = udp_client.SimpleUDPClient(OSC_IP, OSC_PORT)

# --- Message bundling for chords ---
class OSCBundler:
    def __init__(self, client, bundle_time=0.01):
        """
        Creates an OSC bundler that collects messages and sends them as bundles
        
        Args:
            client: The OSC client to send messages through
            bundle_time: Time window to collect messages (in seconds)
        """
        self.client = client
        self.bundle_time = bundle_time
        self.message_queue = []
        self.last_flush_time = time.time()
        self.lock = threading.Lock()
        
        # Start the flush timer thread
        self.running = True
        self.flush_thread = threading.Thread(target=self._flush_timer, daemon=True)
        self.flush_thread.start()
    
    def send_message(self, address, value):
        """Add a message to the current bundle queue"""
        with self.lock:
            self.message_queue.append((address, value))
            
            # If this is first message, update the time
            if len(self.message_queue) == 1:
                self.last_flush_time = time.time()
    
    def flush_bundle(self, force=False):
        """Send all queued messages as a bundle if any exist or if forced"""
        with self.lock:
            current_time = time.time()
            elapsed = current_time - self.last_flush_time
            
            # Only flush if we have messages and either:
            # 1. We're being forced to flush, or
            # 2. Enough time has passed since the first message
            if len(self.message_queue) > 0 and (force or elapsed >= self.bundle_time):
                # Create a new bundle
                bundle_builder = osc_bundle_builder.OscBundleBuilder(
                    osc_bundle_builder.IMMEDIATELY)
                
                # Add all messages to the bundle
                for addr, val in self.message_queue:
                    msg_builder = osc_message_builder.OscMessageBuilder(address=addr)
                    # Handle both single values and lists
                    if isinstance(val, list):
                        for item in val:
                            msg_builder.add_arg(float(item))
                    else:
                        msg_builder.add_arg(float(val))
                    bundle_builder.add_content(msg_builder.build())
                
                # Send the bundle
                bundle = bundle_builder.build()
                self.client.send(bundle)
                
                # Log what we're sending
                if len(self.message_queue) > 1:
                    print(f"OSC → Sent bundle with {len(self.message_queue)} messages")
                else:
                    addr, val = self.message_queue[0]
                    print(f"OSC → {addr} = {val}")
                
                # Clear the queue
                self.message_queue.clear()
                self.last_flush_time = current_time
    
    def _flush_timer(self):
        """Background thread that flushes the bundle periodically"""
        while self.running:
            self.flush_bundle()
            time.sleep(0.001)  # 1ms sleep to avoid hogging CPU
    
    def stop(self):
        """Stop the flush timer thread"""
        self.running = False
        self.flush_thread.join(timeout=0.1)

# Create our bundler
osc_bundler = OSCBundler(osc, bundle_time=0.005)  # 5ms window for collecting chord notes

# --- MIDI Utilities ---
def midi_to_freq(note, pitch_bend=0.0):
    """Convert MIDI note to frequency with pitch bend
    pitch_bend should be in range -1.0 to 1.0 (typically from pitch wheel)
    """
    # Apply pitch bend (default ±2 semitones)
    bend_range = 2.0  # semitones
    note = note + (pitch_bend * bend_range)
    return 440.0 * (2 ** ((note - 69) / 12))

def send_osc(address, value):
    # Make sure address starts with a slash
    if not address.startswith("/"):
        address = "/" + address
    
    # Format for router: /router/command
    full_address = f"/{ROUTER_NAME}{address}"
    
    print(f"OSC → {full_address} = {value}")
    
    # Use the bundler instead of sending directly
    osc_bundler.send_message(full_address, value)

# --- Monophonic note handling ---
class MonophonicNoteManager:
    def __init__(self):
        self.active_notes = {}  # note -> velocity
        self.current_note = None  # Currently sounding note
        self.last_velocity = 0.8  # Default velocity
        self.pitch_bend = 0.0  # Current pitch bend value
        self.sustain_on = False  # Sustain pedal state
        self.sustained_notes = {}  # Notes held by sustain pedal (note -> velocity)
        
        # Chord detection
        self.last_note_time = 0  # Time of last note_on event
        self.is_chord_mode = False  # Whether we're currently in a chord
    
    def note_on(self, note, velocity):
        """Handle note on - update active notes and set current note"""
        self.active_notes[note] = velocity
        self.last_velocity = velocity
        
        # Remove from sustained notes if it was there
        if note in self.sustained_notes:
            del self.sustained_notes[note]
        
        # Detect chord-like input (notes arriving close together)
        now = time.time()
        time_since_last_note = now - self.last_note_time
        self.last_note_time = now
        
        # If notes arrive within 30ms of each other, consider it a chord
        if time_since_last_note < 0.03:
            self.is_chord_mode = True
            print(f"Detected chord-like input (notes {time_since_last_note*1000:.1f}ms apart)")
        else:
            self.is_chord_mode = False
        
        # Instead of complex prioritization logic, just send the note_on to router
        # and let it handle voice allocation
        send_osc("/note_on", [note, velocity])
        return True
    
    def note_off(self, note):
        """Handle note off"""
        # If the note isn't in active notes, nothing to do
        if note not in self.active_notes:
            return False, None
            
        # Track sustain state but always send note_off to router
        # Router will handle sustain logic
        if self.sustain_on:
            # Move note from active to sustained
            self.sustained_notes[note] = self.active_notes[note]
            print(f"Note {note} held by sustain pedal")
        else:
            # With sustain off, remove from active notes
            del self.active_notes[note]
        
        # Send note_off to router - it will decide what to do based on sustain state
        send_osc("/note_off", [note])
        return True, note
    
    def set_pitch_bend(self, value):
        """Set pitch bend value and update current frequency if needed"""
        self.pitch_bend = value
        # Send to router
        send_osc("/pitch_bend", [value])
        return self.current_note
    
    def set_sustain(self, on):
        """Set sustain pedal state"""
        prev_state = self.sustain_on
        self.sustain_on = on
        
        # Send sustain state to router
        send_osc("/sustain", [1 if on else 0])
        
        # If turning sustain off, process any sustained notes
        if prev_state and not on:
            # Clear sustained notes (router will handle actual note-offs)
            self.sustained_notes.clear()
        
        return False, None

# Create note manager
note_manager = MonophonicNoteManager()

# --- MIDI Message Handler ---
def handle_midi_message(msg):
    if msg.type == 'note_on' and msg.velocity > 0:
        # Just pass to note manager, which will send to router
        note_manager.note_on(msg.note, msg.velocity / 127.0)

    elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
        # Pass to note manager, which will send to router
        note_manager.note_off(msg.note)

    elif msg.type == 'polytouch':
        # Handle polyphonic aftertouch
        send_osc("/poly_aftertouch", [msg.note, msg.value / 127.0])
        print(f"Polytouch: {msg.note} pressure {msg.value/127.0:.2f}")

    elif msg.type == 'pitchwheel':
        # Normalize pitch bend range (-8192 to 8191) to -1.0 to +1.0
        bend = msg.pitch / 8192.0
        note_manager.set_pitch_bend(bend)
        print(f"Pitch bend: {bend:.2f}")

    elif msg.type == 'control_change':
        val = msg.value / 127.0
        
        # Handle sustain pedal (CC64)
        if msg.control == 64:  # Sustain pedal
            # Sustain on > 63, off ≤ 63
            sustain_on = msg.value > 63
            note_manager.set_sustain(sustain_on)
            print(f"Sustain pedal: {'ON' if sustain_on else 'OFF'}")
        
        # Send all CC messages to router
        send_osc(f"/cc", [msg.control, val])
        print(f"CC{msg.control}: {val:.2f}")

    # Also handle channel aftertouch (pressure)
    elif msg.type == 'aftertouch':
        send_osc("/aftertouch", [msg.value / 127.0])
        print(f"Channel Aftertouch: {msg.value/127.0:.2f}")

    else:
        print(f"Unhandled MIDI: {msg}")

# --- MIDI Port Selection ---
def select_midi_input():
    input_names = mido.get_input_names()
    if not input_names:
        print("No MIDI input ports found.")
        return None

    print("Available MIDI input ports:")
    for i, name in enumerate(input_names, start=1):
        print(f"{i}: {name}")

    while True:
        choice = input("Select a port number (or 'q' to quit): ").strip()
        if choice.lower() == 'q':
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(input_names):
            return input_names[int(choice) - 1]
        print("Invalid selection. Try again.")

# --- MIDI Listening Loop ---
def main_loop(port_name):
    stop_flag = threading.Event()

    def watch_input():
        while input().strip().lower() != 'q':
            pass
        stop_flag.set()

    print(f"\nOpening port: {port_name}")
    with mido.open_input(port_name) as inport:
        print(f"Listening for MIDI, sending OSC to /{ROUTER_NAME}/* (type 'q' to quit)")
        print("Routing all MIDI events to OSC router")
        print("Sustain and voice allocation handled by router")
        print("Using OSC bundling for improved chord handling (5ms window)")
        
        # Start input watcher thread
        threading.Thread(target=watch_input, daemon=True).start()

        try:
            while not stop_flag.is_set():
                for msg in inport.iter_pending():
                    print(f"MIDI: {msg}")
                    handle_midi_message(msg)
                time.sleep(0.01)
        except KeyboardInterrupt:
            print("Interrupted.")
        finally:
            stop_flag.set()  # Signal threads to exit
            # Stop the bundler
            osc_bundler.stop()
            print("Closed MIDI port.")

# --- Entry Point ---
if __name__ == "__main__":
    port = select_midi_input()
    if port:
        main_loop(port)
    else:
        print("No port selected.") 
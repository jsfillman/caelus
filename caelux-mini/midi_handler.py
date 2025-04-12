import mido
from PyQt5.QtCore import QObject, QTimer, pyqtSignal

class MidiHandler(QObject):
    """
    Handles MIDI input events and routes them to the appropriate components
    """
    note_on_signal = pyqtSignal(int, int)  # note, velocity
    note_off_signal = pyqtSignal(int)      # note
    pitch_bend_signal = pyqtSignal(float)  # normalized value (-1 to 1)
    aftertouch_signal = pyqtSignal(int)    # value (0-127)
    cc_signal = pyqtSignal(int, int)       # controller, value
    
    def __init__(self):
        super().__init__()
        self.midi_port = None
        self.timer = None
        self.active_notes = {}  # Keep track of active notes for polyphonic handling
    
    def open_port(self, port_name):
        """Open a MIDI input port by name"""
        # Close existing port if open
        self.close_port()
        
        try:
            self.midi_port = mido.open_input(port_name)
            print(f"Connected to MIDI device: {port_name}")
            
            # Start polling timer if not already running
            if not self.timer:
                self.timer = QTimer()
                self.timer.timeout.connect(self.poll_midi)
                self.timer.start(5)  # Poll every 5ms for low latency
                
            return True
        except Exception as e:
            print(f"Error connecting to MIDI device: {e}")
            return False
    
    def close_port(self):
        """Close the current MIDI port if open"""
        if self.midi_port:
            self.midi_port.close()
            self.midi_port = None
            
        # Stop the timer
        if self.timer:
            self.timer.stop()
    
    def poll_midi(self):
        """Poll for pending MIDI messages"""
        if not self.midi_port:
            return
            
        for msg in self.midi_port.iter_pending():
            self.process_midi_message(msg)
    
    def process_midi_message(self, msg):
        """Process a single MIDI message"""
        # Note-on with velocity > 0
        if msg.type == 'note_on' and msg.velocity > 0:
            self.active_notes[msg.note] = msg.velocity
            self.note_on_signal.emit(msg.note, msg.velocity)
            
        # Note-off or note-on with velocity 0
        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            if msg.note in self.active_notes:
                del self.active_notes[msg.note]
            self.note_off_signal.emit(msg.note)
            
        # Pitch bend
        elif msg.type == 'pitchwheel':
            # Normalize to -1.0 to 1.0
            normalized = msg.pitch / 8192.0
            self.pitch_bend_signal.emit(normalized)
            
        # Aftertouch (channel pressure)
        elif msg.type == 'aftertouch':
            self.aftertouch_signal.emit(msg.value)
            
        # Poly aftertouch
        elif msg.type == 'polytouch':
            # We'll handle this the same as channel pressure for now
            self.aftertouch_signal.emit(msg.value)
            
        # Control change
        elif msg.type == 'control_change':
            self.cc_signal.emit(msg.control, msg.value)
            
            # Special case for sustain pedal (CC 64)
            if msg.control == 64:
                self.handle_sustain(msg.value)
    
    def handle_sustain(self, value):
        """Special handling for sustain pedal"""
        # For now, this is handled directly in the audio engine through the CC signal
        pass

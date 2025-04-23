"""
Voice class for managing individual synth voice instances
"""
from pythonosc import udp_client
from lib.common.utils import DEFAULT_SYNTH_HOST, DEFAULT_SYNTH_NAME, midi_to_freq, LOG

class Voice:
    """Represents a voice instance with its state"""
    def __init__(self, voice_id, port, host=DEFAULT_SYNTH_HOST, synth_name=DEFAULT_SYNTH_NAME):
        self.id = voice_id
        self.port = port
        self.host = host
        self.synth_name = synth_name
        self.note = None
        self.velocity = 0
        self.is_active = False
        self.client = udp_client.SimpleUDPClient(self.host, port)
    
    def __repr__(self):
        return f"Voice(id={self.id}, port={self.port}, host={self.host}, note={self.note}, active={self.is_active})"
    
    def note_on(self, note, velocity):
        """Send note-on messages to this voice"""
        self.note = note
        self.velocity = velocity
        self.is_active = True
        
        # Send the three standard synth parameters
        self.send_osc("/freq", midi_to_freq(note))
        self.send_osc("/gain", velocity)
        self.send_osc("/gate", 1)
        
        LOG.debug(f"Voice {self.id} note ON: {note} vel: {velocity:.2f}")
        return True
    
    def note_off(self):
        """Send note-off message to this voice"""
        if self.is_active:
            # Send gate off
            self.send_osc("/gate", 0)
            
            # Also send an all-notes-off message as a backup
            self.send_osc("/allNotesOff", 1)
            
            # For extra safety, send a direct OSC panic to this specific voice
            self.send_osc("/panic", 1)
            
            self.is_active = False
            LOG.debug(f"Voice {self.id} note OFF: {self.note}")
            return True
        return False
    
    def reset(self):
        """Reset this voice to idle state"""
        self.note_off()
        self.note = None
        self.velocity = 0
        return True
        
    def set_cc(self, cc_num, value):
        """Send CC message to this voice"""
        # Send specific CC value
        self.send_osc(f"/cc{cc_num}", value)
        
        # Special handling for sustain pedal
        if cc_num == 64:
            # Also send to dedicated sustain parameter if it exists
            self.send_osc("/sustain", 1.0 if value >= 0.5 else 0.0)
        
        return True
    
    def set_sustain(self, value):
        """Send sustain directly (0.0-1.0)"""
        self.send_osc("/sustain", value)
        return True
    
    def set_param(self, param, value):
        """Send generic parameter to this voice"""
        self.send_osc(f"/{param}", value)
        return True
        
    def send_osc(self, path, value):
        """Send OSC message to this voice's synth instance"""
        if not path.startswith("/"):
            path = "/" + path
            
        # Format: /synthName/param
        full_path = f"/{self.synth_name}{path}"
        
        # Ensure value is float for Faust
        if isinstance(value, (int, float)):
            value = float(value)
        
        LOG.info(f"Voice {self.id}: Sending OSC message {full_path} = {value} to {self.host}:{self.port}")
        
        try:
            self.client.send_message(full_path, value)
            return True
        except Exception as e:
            LOG.error(f"Error sending OSC to voice {self.id} ({self.host}:{self.port}): {e}")
            return False 
"""
Voice class for managing individual synth voice instances.

Because even synths need their personal space - one voice per instance,
living in harmony on different ports.
"""
from typing import Optional, Union, Any

from pythonosc import udp_client
from lib.common.utils import DEFAULT_SYNTH_HOST, DEFAULT_SYNTH_NAME, midi_to_freq, LOG

class Voice:
    """
    Represents a single synth voice instance with its state.
    
    Think of this as the digital equivalent of a single key on a piano,
    except it can only play one note at a time. It's not multitasking,
    it's focusing on doing one thing really well.
    """
    
    def __init__(
        self,
        voice_id: int,
        port: int,
        host: str = DEFAULT_SYNTH_HOST,
        synth_name: str = DEFAULT_SYNTH_NAME
    ) -> None:
        """
        Initialize a voice instance.
        
        Assigns this voice its digital identity and address.
        No existential crisis here, just pure purpose.
        
        Args:
            voice_id: Unique identifier for this voice
            port: OSC port number to communicate with this voice
            host: Hostname or IP address where the synth is running
            synth_name: Name of the synth to include in OSC paths
        """
        self.id: int = voice_id
        self.port: int = port
        self.host: str = host
        self.synth_name: str = synth_name
        self.note: Optional[int] = None
        self.velocity: float = 0
        self.is_active: bool = False
        self.client = udp_client.SimpleUDPClient(self.host, port)
    
    def __repr__(self) -> str:
        """Return string representation - for debugging and those existential moments."""
        return f"Voice(id={self.id}, port={self.port}, host={self.host}, note={self.note}, active={self.is_active})"
    
    def note_on(self, note: int, velocity: float) -> bool:
        """
        Send note-on messages to this voice.
        
        The digital equivalent of pressing a key - with feeling!
        
        Args:
            note: MIDI note number (0-127)
            velocity: Note velocity (0.0-1.0) - how hard you hit the key
            
        Returns:
            True if message was sent successfully
        """
        self.note = note
        self.velocity = velocity
        self.is_active = True
        
        # The holy trinity of synth parameters
        self.send_osc("/freq", midi_to_freq(note))
        self.send_osc("/gain", velocity)
        self.send_osc("/gate", 1)
        
        LOG.debug(f"Voice {self.id} note ON: {note} vel: {velocity:.2f}")
        return True
    
    def note_off(self) -> bool:
        """
        Send note-off message to this voice.
        
        The digital equivalent of letting go of a key.
        We're really paranoid about stuck notes, so we
        send the "shut up" command in three different ways.
        
        Returns:
            True if note-off was sent, False if voice was not active
        """
        if self.is_active:
            # Send gate off
            self.send_osc("/gate", 0)
            
            # Belt and suspenders approach - better safe than sorry
            self.send_osc("/allNotesOff", 1)
            
            # And a fire extinguisher, just in case
            self.send_osc("/panic", 1)
            
            self.is_active = False
            LOG.debug(f"Voice {self.id} note OFF: {self.note}")
            return True
        return False
    
    def reset(self) -> bool:
        """
        Reset this voice to idle state.
        
        The digital equivalent of "have you tried turning it off and on again?"
        
        Returns:
            True if reset was successful
        """
        self.note_off()
        self.note = None
        self.velocity = 0
        return True
        
    def set_cc(self, cc_num: int, value: float) -> bool:
        """
        Send CC message to this voice.
        
        All those knobs and sliders have to do something, right?
        
        Args:
            cc_num: MIDI CC number
            value: CC value (0.0-1.0)
            
        Returns:
            True if message was sent successfully
        """
        # Send specific CC value
        self.send_osc(f"/cc{cc_num}", value)
        
        # Special handling for sustain pedal
        if cc_num == 64:
            # Also send to dedicated sustain parameter if it exists
            self.send_osc("/sustain", 1.0 if value >= 0.5 else 0.0)
        
        return True
    
    def set_sustain(self, value: float) -> bool:
        """
        Send sustain pedal state directly.
        
        For when you want notes to hang around after the party's over.
        
        Args:
            value: Sustain value (0.0-1.0)
            
        Returns:
            True if message was sent successfully
        """
        self.send_osc("/sustain", value)
        return True
    
    def set_param(self, param: str, value: Any) -> bool:
        """
        Send generic parameter to this voice.
        
        The Swiss Army knife of parameter setting.
        
        Args:
            param: Parameter name (without leading /)
            value: Parameter value
            
        Returns:
            True if message was sent successfully
        """
        self.send_osc(f"/{param}", value)
        return True
        
    def send_osc(self, path: str, value: Any) -> bool:
        """
        Send OSC message to this voice's synth instance.
        
        The digital postal service - neither snow nor rain nor
        heat nor gloom of night stays these packets from their
        appointed route.
        
        Args:
            path: OSC path (with or without leading /)
            value: Value to send
            
        Returns:
            True if message was sent successfully, False on error
        """
        if not path.startswith("/"):
            path = "/" + path
            
        # Format: /synthName/param
        full_path = f"/{self.synth_name}{path}"
        
        # Convert boolean values to integers (0/1)
        if isinstance(value, bool):
            value = 1 if value else 0
        # Ensure value is float for Faust
        elif isinstance(value, (int, float)):
            value = float(value)
        
        # Add extra debug info for important parameters
        if path in ["/freq", "/cutoff", "/mod_depth", "/pitch_bend_range"]:
            LOG.info(f"Voice {self.id}: Sending IMPORTANT OSC message {full_path} = {value} to {self.host}:{self.port}")
        else:
            LOG.debug(f"Voice {self.id}: Sending OSC message {full_path} = {value} to {self.host}:{self.port}")
        
        try:
            # Validate client is properly initialized
            if not hasattr(self, 'client') or self.client is None:
                LOG.error(f"Voice {self.id}: OSC client is None or not initialized")
                return False
                
            # Validate host and port are set correctly
            LOG.debug(f"Voice {self.id}: OSC client targeting {self.host}:{self.port}")
            
            # Validate message format before sending
            LOG.debug(f"Voice {self.id}: OSC message details - path: {full_path}, value type: {type(value)}, value: {value}")
            
            # Send the message
            self.client.send_message(full_path, value)
            return True
        except Exception as e:
            LOG.error(f"Error sending OSC to voice {self.id} ({self.host}:{self.port}): {e}")
            import traceback
            LOG.error(f"Stack trace: {traceback.format_exc()}")
            return False 
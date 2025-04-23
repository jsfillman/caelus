"""
Voice class for managing individual synth voice instances.

This module provides the Voice class which handles communication with a single synth
voice instance via OSC messages.
"""
from typing import Optional, Union, Any

from pythonosc import udp_client
from lib.common.utils import DEFAULT_SYNTH_HOST, DEFAULT_SYNTH_NAME, midi_to_freq, LOG

class Voice:
    """
    Represents a single synth voice instance with its state.
    
    This class encapsulates all the state and behavior related to a single voice
    in a polyphonic synthesizer, including sending OSC messages to control it.
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
        """Return string representation of the voice."""
        return f"Voice(id={self.id}, port={self.port}, host={self.host}, note={self.note}, active={self.is_active})"
    
    def note_on(self, note: int, velocity: float) -> bool:
        """
        Send note-on messages to this voice.
        
        Args:
            note: MIDI note number (0-127)
            velocity: Note velocity (0.0-1.0)
            
        Returns:
            True if message was sent successfully
        """
        self.note = note
        self.velocity = velocity
        self.is_active = True
        
        # Send the three standard synth parameters
        self.send_osc("/freq", midi_to_freq(note))
        self.send_osc("/gain", velocity)
        self.send_osc("/gate", 1)
        
        LOG.debug(f"Voice {self.id} note ON: {note} vel: {velocity:.2f}")
        return True
    
    def note_off(self) -> bool:
        """
        Send note-off message to this voice.
        
        Returns:
            True if note-off was sent, False if voice was not active
        """
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
    
    def reset(self) -> bool:
        """
        Reset this voice to idle state.
        
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
        
        # Ensure value is float for Faust
        if isinstance(value, (int, float)):
            value = float(value)
        
        # Add extra debug info for important parameters
        if path in ["/freq", "/cutoff", "/mod_depth", "/pitch_bend_range"]:
            LOG.info(f"Voice {self.id}: Sending IMPORTANT OSC message {full_path} = {value} to {self.host}:{self.port}")
        else:
            LOG.debug(f"Voice {self.id}: Sending OSC message {full_path} = {value} to {self.host}:{self.port}")
        
        try:
            self.client.send_message(full_path, value)
            return True
        except Exception as e:
            LOG.error(f"Error sending OSC to voice {self.id} ({self.host}:{self.port}): {e}")
            return False 
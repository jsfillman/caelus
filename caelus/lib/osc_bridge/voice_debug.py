"""
Debugging version of Voice class for OSC Router.

This version adds extra debug logging to help diagnose OSC message routing issues.
"""
import os
import sys
import logging
from typing import Optional, Union, Any

from pythonosc import udp_client

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, parent_dir)

from lib.common.utils import DEFAULT_SYNTH_HOST, DEFAULT_SYNTH_NAME, midi_to_freq, LOG

# Set up enhanced logging
LOG.setLevel(logging.DEBUG)
# Add a stream handler if there isn't one already
if not LOG.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    LOG.addHandler(handler)

class VoiceDebug:
    """
    Debug version of Voice class with extra logging.
    Represents a single synth voice instance with its state.
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
        
        # Debug logging
        LOG.debug(f"VOICE DEBUG: Created voice id={voice_id}, port={port}, host={host}, synth_name={synth_name}")
    
    def __repr__(self) -> str:
        """Return string representation - for debugging and those existential moments."""
        return f"Voice(id={self.id}, port={self.port}, host={self.host}, note={self.note}, active={self.is_active})"
    
    def note_on(self, note: int, velocity: float) -> bool:
        """
        Send note-on messages to this voice.
        
        Args:
            note: MIDI note number (0-127)
            velocity: Note velocity (0.0-1.0) - how hard you hit the key
            
        Returns:
            True if message was sent successfully
        """
        LOG.debug(f"VOICE DEBUG: note_on called with note={note}, velocity={velocity}")
        LOG.debug(f"VOICE DEBUG: Voice state before note_on: id={self.id}, port={self.port}, is_active={self.is_active}, note={self.note}")
        
        self.note = note
        self.velocity = velocity
        self.is_active = True
        
        # Calculate frequency
        freq = midi_to_freq(note)
        LOG.debug(f"VOICE DEBUG: Calculated frequency: {freq} Hz for note {note}")
        
        # The holy trinity of synth parameters
        freq_result = self.send_osc("/freq", freq)
        gain_result = self.send_osc("/gain", velocity)
        gate_result = self.send_osc("/gate", 1)
        
        success = freq_result and gain_result and gate_result
        
        LOG.debug(f"VOICE DEBUG: Voice state after note_on: id={self.id}, port={self.port}, is_active={self.is_active}, note={self.note}")
        LOG.debug(f"VOICE DEBUG: note_on results: freq={freq_result}, gain={gain_result}, gate={gate_result}")
        
        if success:
            LOG.debug(f"Voice {self.id} note ON: {note} vel: {velocity:.2f}")
        else:
            LOG.error(f"VOICE DEBUG: Failed to send note_on messages for note {note}")
            
        return success
    
    def note_off(self) -> bool:
        """
        Send note-off message to this voice.
        
        Returns:
            True if note-off was sent, False if voice was not active
        """
        LOG.debug(f"VOICE DEBUG: note_off called for voice {self.id}")
        LOG.debug(f"VOICE DEBUG: Voice state before note_off: id={self.id}, port={self.port}, is_active={self.is_active}, note={self.note}")
        
        if self.is_active:
            # Send gate off
            result1 = self.send_osc("/gate", 0)
            
            # Belt and suspenders approach - better safe than sorry
            result2 = self.send_osc("/allNotesOff", 1)
            
            # And a fire extinguisher, just in case
            result3 = self.send_osc("/panic", 1)
            
            success = result1 and result2 and result3
            
            self.is_active = False
            
            LOG.debug(f"VOICE DEBUG: note_off results: gate={result1}, allNotesOff={result2}, panic={result3}")
            LOG.debug(f"VOICE DEBUG: Voice state after note_off: id={self.id}, port={self.port}, is_active={self.is_active}, note={self.note}")
            
            if success:
                LOG.debug(f"Voice {self.id} note OFF: {self.note}")
            else:
                LOG.error(f"VOICE DEBUG: Failed to send note_off messages for voice {self.id}")
                
            return success
        
        LOG.debug(f"VOICE DEBUG: note_off called but voice {self.id} is not active")
        return False
    
    def reset(self) -> bool:
        """
        Reset this voice to idle state.
        
        Returns:
            True if reset was successful
        """
        LOG.debug(f"VOICE DEBUG: reset called for voice {self.id}")
        
        result = self.note_off()
        self.note = None
        self.velocity = 0
        
        LOG.debug(f"VOICE DEBUG: reset completed with result={result}")
        return result
    
    def set_param(self, param: str, value: Any) -> bool:
        """
        Send generic parameter to this voice.
        
        Args:
            param: Parameter name (without leading /)
            value: Parameter value
            
        Returns:
            True if message was sent successfully
        """
        LOG.debug(f"VOICE DEBUG: set_param called with param={param}, value={value}")
        result = self.send_osc(f"/{param}", value)
        LOG.debug(f"VOICE DEBUG: set_param result: {result}")
        return result
    
    def send_osc(self, path: str, value: Any) -> bool:
        """
        Send OSC message to this voice's synth instance.
        
        Args:
            path: OSC path (with or without leading /)
            value: Value to send
            
        Returns:
            True if message was sent successfully, False on error
        """
        LOG.debug(f"VOICE DEBUG: send_osc called with path={path}, value={value}")
        
        # Normalize path: ensure it has no leading slash
        if path.startswith("/"):
            # Remove the leading slash since we'll add it back in the full path
            path = path[1:]
            
        # Create the properly formatted OSC path: /synthName/param
        full_path = f"/{self.synth_name}/{path}"
        
        # Log the path transformation for debugging
        LOG.debug(f"VOICE DEBUG: Created OSC path: '{full_path}' for parameter '{path}'")
        
        # Convert boolean values to integers (0/1)
        if isinstance(value, bool):
            value = 1 if value else 0
        # Ensure value is float for Faust
        elif isinstance(value, (int, float)):
            value = float(value)
        
        # Add extra debug info for important parameters
        if path in ["freq", "cutoff", "mod_depth", "pitch_bend_range"]:
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
            LOG.debug(f"VOICE DEBUG: Message sent successfully to {self.host}:{self.port}")
            return True
            
        except Exception as e:
            LOG.error(f"Error sending OSC to voice {self.id} ({self.host}:{self.port}): {e}")
            import traceback
            LOG.error(f"Stack trace: {traceback.format_exc()}")
            return False

def main():
    """Simple test main function"""
    import argparse
    import time
    
    parser = argparse.ArgumentParser(description="Test Voice Debug")
    parser.add_argument("--port", type=int, default=5510, help="Synth port (default: 5510)")
    parser.add_argument("--name", type=str, default="simple", help="Synth name (default: simple)")
    
    args = parser.parse_args()
    
    # Create a test voice
    voice = VoiceDebug(1, args.port, synth_name=args.name)
    
    try:
        # Play a test note
        LOG.info("Playing test note (middle C)...")
        voice.note_on(60, 0.8)
        
        # Wait 1 second
        time.sleep(1)
        
        # Send note off
        LOG.info("Turning off note...")
        voice.note_off()
        
        LOG.info("Test completed!")
        
    except KeyboardInterrupt:
        LOG.info("Test interrupted")
        voice.note_off()

if __name__ == "__main__":
    main()
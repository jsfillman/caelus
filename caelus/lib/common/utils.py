"""
Common utility functions for the OSC router system.

The unsung heroes of the codebase - small but mighty utilities
that keep everything running smoothly.
"""
import logging
from typing import Final, Optional, Union

# Set up logging - because print statements are so 2010
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
LOG: Final = logging.getLogger(__name__)

# Constants - because magic numbers are the root of all evil
DEFAULT_ROUTER_PORT: Final[int] = 9000
DEFAULT_SYNTH_HOST: Final[str] = "127.0.0.1"
DEFAULT_SYNTH_NAME: Final[str] = "simple"

def midi_to_freq(note: Union[int, float], pitch_bend: float = 0.0, bend_range: float = 2.0) -> float:
    """
    Convert MIDI note number to frequency in Hz with optional pitch bend.
    
    The magic formula that makes your keyboard go bleep bloop at the right pitches.
    A440 tuning assumed - sorry, 432Hz conspiracy theorists!
    
    Args:
        note: MIDI note number (0-127)
        pitch_bend: Pitch bend value in range -1.0 to 1.0
        bend_range: Pitch bend range in semitones (default: ±2 semitones)
        
    Returns:
        Frequency in Hz
    """
    # Apply pitch bend (configurable range)
    note = note + (pitch_bend * bend_range)
    return 440.0 * (2 ** ((note - 69) / 12)) 
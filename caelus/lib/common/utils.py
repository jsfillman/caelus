"""
Common utility functions for the OSC router system.

This module provides shared constants and utility functions used across the OSC router system.
"""
import logging
from typing import Final, Optional, Union

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
LOG: Final = logging.getLogger(__name__)

# Default settings that can be used across modules
DEFAULT_ROUTER_PORT: Final[int] = 9000
DEFAULT_SYNTH_HOST: Final[str] = "127.0.0.1"
DEFAULT_SYNTH_NAME: Final[str] = "simple"

def midi_to_freq(note: Union[int, float], pitch_bend: float = 0.0, bend_range: float = 2.0) -> float:
    """
    Convert MIDI note number to frequency in Hz with optional pitch bend.
    
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
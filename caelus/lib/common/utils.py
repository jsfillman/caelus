"""
Common utility functions for the OSC router system
"""
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
LOG = logging.getLogger(__name__)

# Default settings that can be used across modules
DEFAULT_ROUTER_PORT = 9000
DEFAULT_SYNTH_HOST = "127.0.0.1"
DEFAULT_SYNTH_NAME = "simple"

def midi_to_freq(note, pitch_bend=0.0, bend_range=2.0):
    """Convert MIDI note to frequency with pitch bend
    pitch_bend should be in range -1.0 to 1.0 (typically from pitch wheel)
    bend_range is the range in semitones (default ±2 semitones)
    """
    # Apply pitch bend (configurable range)
    note = note + (pitch_bend * bend_range)
    return 440.0 * (2 ** ((note - 69) / 12)) 
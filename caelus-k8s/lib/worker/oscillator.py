#!/usr/bin/env python3
"""
Oscillator module for Caelus K8s worker.
"""

import logging
import numpy as np
from pyo import Server, Sine, TableWrite, NewTable, SndTable

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SineOscillator:
    """Simple sine wave oscillator using Pyo."""
    
    def __init__(self, sr=44100, buffer_size=256, buffer_count=8):
        """Initialize the oscillator.
        
        Args:
            sr (int): Sample rate
            buffer_size (int): Buffer size for audio processing
            buffer_count (int): Number of buffers in audio queue
        """
        self.sr = sr
        self.buffer_size = buffer_size
        self.buffer_count = buffer_count
        
        # Map of active notes to their properties
        self.active_notes = {}  # note -> (frequency, amplitude)
        
        logger.info("Sine oscillator initialized")
    
    def note_to_freq(self, note):
        """Convert MIDI note to frequency.
        
        Args:
            note (int): MIDI note number (0-127)
            
        Returns:
            float: Frequency in Hz
        """
        return 440.0 * (2.0 ** ((note - 69) / 12.0))
    
    def start_note(self, note, velocity):
        """Start playing a note.
        
        Args:
            note (int): MIDI note number (0-127)
            velocity (int): MIDI velocity (0-127)
            
        Returns:
            numpy.ndarray: Generated audio buffer
        """
        # Calculate frequency and amplitude
        freq = self.note_to_freq(note)
        amp = velocity / 127.0
        
        # Store note information
        self.active_notes[note] = (freq, amp)
        
        # Generate a simple sine wave using numpy
        duration = 0.2  # 200ms buffer
        t = np.linspace(0, duration, int(self.sr * duration), False)
        audio_data = amp * np.sin(2 * np.pi * freq * t)
        
        logger.info(f"Generated sine wave for note {note} (freq: {freq:.2f} Hz, amp: {amp:.2f})")
        return audio_data
    
    def stop_note(self, note):
        """Stop playing a note.
        
        Args:
            note (int): MIDI note number (0-127)
            
        Returns:
            numpy.ndarray: Release envelope buffer (empty for now)
        """
        if note in self.active_notes:
            # Get note properties
            freq, amp = self.active_notes[note]
            
            # Remove note from active notes
            del self.active_notes[note]
            
            # Create a short release envelope - fade out over 50ms
            duration = 0.05  # 50ms
            samples = int(self.sr * duration)
            
            # Linear fade out
            envelope = np.linspace(amp, 0, samples)
            t = np.linspace(0, duration, samples, False)
            release_buffer = envelope * np.sin(2 * np.pi * freq * t)
            
            logger.info(f"Stopped note {note}, generated release buffer")
            return release_buffer
        
        logger.warning(f"Note {note} not playing")
        return np.zeros(int(0.01 * self.sr))  # Short silence if note not found
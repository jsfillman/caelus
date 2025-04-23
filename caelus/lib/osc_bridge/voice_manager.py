"""
Voice allocation and management for polyphonic synth.

This module provides classes for managing voice allocation in a polyphonic synthesizer system:
- NoteTracker: Tracks active and sustained notes
- VoiceManager: Main manager for allocating voices to incoming MIDI notes
"""
from typing import Dict, List, Set, Optional, Any, Tuple

from lib.common.utils import LOG, midi_to_freq
from lib.osc_bridge.voice import Voice


class NoteTracker:
    """
    Tracks note allocation state for polyphonic synth voices.
    
    This class maintains the mapping between MIDI notes and voices, as well as
    tracking sustained notes and note-off events during sustain.
    """
    
    def __init__(self) -> None:
        """Initialize the note tracker."""
        self.active_notes: Dict[int, int] = {}  # Maps MIDI note number to voice ID
        self.sustained_notes: Set[int] = set()  # Notes being sustained
        self.note_off_cache: Dict[int, int] = {}  # Cache for note-off events while sustain is active
        self.sustain_active: bool = False
    
    def is_note_active(self, note: int) -> bool:
        """
        Check if a note is currently active (being played or sustained).
        
        Args:
            note: MIDI note number
            
        Returns:
            True if the note is active
        """
        return note in self.active_notes
    
    def get_voice_for_note(self, note: int) -> Optional[int]:
        """
        Get the voice ID assigned to a note.
        
        Args:
            note: MIDI note number
            
        Returns:
            Voice ID if found, None otherwise
        """
        return self.active_notes.get(note)
    
    def assign_note_to_voice(self, note: int, voice_idx: int) -> None:
        """
        Assign a note to a specific voice.
        
        Args:
            note: MIDI note number
            voice_idx: Voice ID
        """
        self.active_notes[note] = voice_idx
        LOG.debug(f"Assigned note {note} to voice {voice_idx}")
    
    def release_note(self, note: int) -> None:
        """
        Remove a note from all tracking collections.
        
        Args:
            note: MIDI note number
        """
        if note in self.active_notes:
            del self.active_notes[note]
        if note in self.sustained_notes:
            self.sustained_notes.remove(note)
        if note in self.note_off_cache:
            del self.note_off_cache[note]


class VoiceManager:
    """
    Manages allocation of voices for a polyphonic synthesizer.
    
    This class handles voice allocation, note on/off events, sustain pedal,
    and continuous controller (CC) management.
    """
    
    def __init__(self, voices: List[Voice]) -> None:
        """
        Initialize with a list of Voice instances.
        
        Args:
            voices: List of Voice objects representing available synth voices
        """
        self.voices: List[Voice] = voices
        self.note_tracker: NoteTracker = NoteTracker()
        self.cc_values: Dict[int, float] = {}  # Store CC values
        
        # Default controller values
        self.cc_defaults: Dict[int, float] = {
            1: 0,  # Modulation wheel default (0)
        }
        
        # Filter cutoff control
        self.default_cutoff: float = 1000.0  # Default filter cutoff value
        self.current_cutoff: float = self.default_cutoff
        self.mod_wheel_value: float = 0.0
        self.expression_value: float = 0.0
        
        # Initialize pitch bend value
        self.pitch_bend: float = 0.0
        
        # Prepare voices
        for voice in self.voices:
            voice.reset()
    
    @property
    def active_notes(self) -> Dict[int, int]:
        """Get active notes mapping from the note tracker."""
        return self.note_tracker.active_notes
    
    @property
    def sustained_notes(self) -> Set[int]:
        """Get sustained notes set from the note tracker."""
        return self.note_tracker.sustained_notes
    
    @property
    def note_off_cache(self) -> Dict[int, int]:
        """Get note-off cache from the note tracker."""
        return self.note_tracker.note_off_cache
    
    @property
    def sustain_active(self) -> bool:
        """Get sustain active state from the note tracker."""
        return self.note_tracker.sustain_active
    
    @sustain_active.setter
    def sustain_active(self, value: bool) -> None:
        """Set sustain active state in the note tracker."""
        self.note_tracker.sustain_active = value
    
    def allocate_voice(self, note_num: int) -> Optional[Voice]:
        """
        Allocate an available voice to a note number.
        
        Args:
            note_num: MIDI note number to allocate
            
        Returns:
            Voice object if allocation successful, None otherwise
        """
        # Check if note is already playing
        if note_num in self.active_notes:
            voice_idx = self.active_notes[note_num]
            LOG.info(f"Note {note_num} already allocated to voice {voice_idx}, reusing")
            return self.voices[voice_idx]
        
        # Find available voice
        free_voice: Optional[Voice] = None
        for i, voice in enumerate(self.voices):
            if not voice.is_active:
                free_voice = voice
                self.note_tracker.assign_note_to_voice(note_num, i)
                LOG.debug(f"Allocated voice {i} to note {note_num}")
                break
        
        # If no free voice, steal oldest
        if free_voice is None and self.voices:
            LOG.warning(f"No free voices available for note {note_num}, stealing oldest voice")
            
            # Find the oldest voice (first one in our list - this is a simplistic approach)
            oldest_voice_idx = 0
            oldest_voice = self.voices[oldest_voice_idx]
            stolen_note = oldest_voice.note
            
            # Log the voice stealing
            LOG.info(f"Stealing voice {oldest_voice_idx} from note {stolen_note}")
            
            # Send note-off to the stolen voice
            if stolen_note is not None:
                # Clean up mapping for the stolen note
                self.note_tracker.release_note(stolen_note)
                
                # Send multiple note-off commands to ensure it's really off
                oldest_voice.note_off()
                oldest_voice.send_osc("/gate", 0)
                oldest_voice.send_osc("/allNotesOff", 1)
            
            # Assign the voice to the new note
            self.note_tracker.assign_note_to_voice(note_num, oldest_voice_idx)
            free_voice = oldest_voice
            
            # Double-check that the voice is properly marked as not active
            # This ensures it can be reactivated
            free_voice.is_active = False
        
        # Log voice allocation state
        LOG.debug(f"Voice allocation: {len(self.active_notes)} active notes, " +
                  f"{len(self.voices) - len([v for v in self.voices if v.is_active])} free voices")
        
        return free_voice
    
    def note_on(self, note_num: int, velocity: float) -> bool:
        """
        Process note-on for a specific note number.
        
        Args:
            note_num: MIDI note number
            velocity: Note velocity (0.0-1.0)
            
        Returns:
            True if note-on was successful
        """
        # If note was in sustain cache, remove it
        if note_num in self.note_off_cache:
            del self.note_off_cache[note_num]
            
        # If note was in sustained notes, remove it
        if note_num in self.sustained_notes:
            self.sustained_notes.remove(note_num)
        
        # If note is already active, send note-off to that voice first
        if note_num in self.active_notes:
            old_voice_idx = self.active_notes[note_num]
            old_voice = self.voices[old_voice_idx]
            LOG.info(f"Note {note_num} already active on voice {old_voice_idx}, sending note-off first")
            old_voice.note_off()
        
        voice = self.allocate_voice(note_num)
        if voice:
            voice.note_on(note_num, velocity)
            LOG.info(f"Note ON: {note_num} velocity: {velocity:.2f}")
            return True
        
        LOG.warning(f"Could not allocate voice for note {note_num}")
        return False
    
    def note_off(self, note_num: int) -> None:
        """
        Turn off a note.
        
        Args:
            note_num: MIDI note number
        """
        # Check if this note is active
        if note_num in self.active_notes:
            voice_idx = self.active_notes[note_num]
            
            # If sustain is active, cache the note-off but DO NOT remove from active_notes
            if self.sustain_active:
                LOG.info(f"Sustaining note {note_num} on voice {voice_idx}")
                self.sustained_notes.add(note_num) 
                self.note_off_cache[note_num] = voice_idx
                # We don't delete from active_notes while sustain is active
                # This ensures we can track which voices are playing which notes
            else:
                # Process the note-off immediately
                self._process_note_off(note_num, voice_idx)
        else:
            LOG.info(f"Note {note_num} not active, ignoring note-off")
    
    def _process_note_off(self, note: int, voice_idx: int) -> None:
        """
        Actually process a note-off event.
        
        Args:
            note: MIDI note number
            voice_idx: Voice ID
        """
        LOG.info(f"Turning off note {note} on voice {voice_idx}")
        
        # Get the voice
        if voice_idx >= len(self.voices):
            LOG.error(f"Voice index {voice_idx} out of range")
            return
            
        voice = self.voices[voice_idx]
        
        # Send note-off to the voice
        if voice:
            voice.note_off()
        
        # Remove the note from all tracking collections
        self.note_tracker.release_note(note)
    
    def set_sustain(self, value: float) -> None:
        """
        Set the sustain pedal state.
        
        Args:
            value: Sustain value (0-127 or 0.0-1.0)
        """
        # Convert 0-1 float to on/off (if coming from OSC)
        if value <= 1.0:
            value = 127 if value >= 0.5 else 0
            
        # Sustain is active if value is 63 or higher
        new_sustain_state = value >= 63
        
        # If sustain state hasn't changed, do nothing
        if self.sustain_active == new_sustain_state:
            return
            
        # If sustain was on and is now turned off
        if self.sustain_active and not new_sustain_state:
            LOG.info(f"Sustain OFF - releasing {len(self.note_off_cache)} sustained notes")
            
            # Process all cached note-offs while keeping the dict intact during iteration
            for note, voice_idx in list(self.note_off_cache.items()):
                # Only process if the note is in sustained_notes
                if note in self.sustained_notes:
                    # Actually send the note_off and update tracking
                    self._process_note_off(note, voice_idx)
                    LOG.debug(f"Released sustained note {note}")
            
            # Clear cache and sustained notes
            self.note_off_cache.clear()
            self.sustained_notes.clear()
        elif not self.sustain_active and new_sustain_state:
            LOG.info("Sustain ON")
        
        # Update sustain state
        self.sustain_active = new_sustain_state
    
    def set_pitch_bend(self, value: float) -> None:
        """
        Set the pitch bend value and update all active voices.
        
        Args:
            value: Pitch bend value (normalized to -1.0 to 1.0)
        """
        self.pitch_bend = value
        
        # Apply pitch bend to all active voices
        for note, voice_idx in self.active_notes.items():
            voice = self.voices[voice_idx]
            # Only update voices that are playing a note
            if voice.note is not None:
                # Calculate the new frequency with the pitch bend applied
                new_freq = midi_to_freq(voice.note, self.pitch_bend)
                voice.send_osc("/freq", new_freq)
    
    def all_notes_off(self) -> None:
        """
        Turn off all active notes.
        """
        LOG.info("All notes off")
        
        # Process active notes
        for note, voice_idx in list(self.active_notes.items()):
            voice = self.voices[voice_idx]
            voice.note_off()
        
        # Clear all note tracking
        self.active_notes.clear()
        self.sustained_notes.clear()
        self.note_off_cache.clear()
        
        # Reset sustain
        self.sustain_active = False
    
    def set_cc(self, cc_num: int, value: float) -> None:
        """
        Set a MIDI continuous controller value.
        
        Args:
            cc_num: MIDI CC number
            value: CC value (0.0-1.0)
        """
        # Store the CC value
        self.cc_values[cc_num] = value
        
        # Handle specific CC numbers
        if cc_num == 1:  # Modulation wheel
            self.mod_wheel_value = value
            self._update_filter_cutoff()
        elif cc_num == 11:  # Expression
            self.expression_value = value
            self._update_filter_cutoff()
        elif cc_num == 64:  # Sustain pedal
            self.set_sustain(value)
        
        # Forward CC to all active voices
        for _, voice_idx in self.active_notes.items():
            voice = self.voices[voice_idx]
            voice.set_cc(cc_num, value)
    
    def _update_filter_cutoff(self) -> None:
        """
        Update filter cutoff based on mod wheel and expression.
        """
        # Simple algorithm: default + mod_wheel * 2000 + expression * 1000
        mod_effect = self.mod_wheel_value * 2000.0
        expr_effect = self.expression_value * 1000.0
        
        # Calculate new cutoff
        new_cutoff = self.default_cutoff + mod_effect + expr_effect
        
        # Clamp cutoff within reasonable ranges
        new_cutoff = max(50.0, min(20000.0, new_cutoff))
        
        # Only update if significantly changed
        if abs(new_cutoff - self.current_cutoff) > 0.1:
            self.current_cutoff = new_cutoff
            
            LOG.info(f"Updated cutoff to {new_cutoff:.1f} Hz (mod: {self.mod_wheel_value:.2f}, expr: {self.expression_value:.2f})")
            
            # Apply to all active voices
            for _, voice_idx in self.active_notes.items():
                voice = self.voices[voice_idx]
                voice.set_param("cutoff", new_cutoff)
    
    def reset_all_controllers(self) -> None:
        """
        Reset all controllers to their default values.
        """
        # Reset pitch bend
        self.pitch_bend = 0.0
        
        # Reset continuous controllers to defaults
        for cc_num, default_value in self.cc_defaults.items():
            self.set_cc(cc_num, default_value)
        
        # Reset sustain
        if self.sustain_active:
            self.set_sustain(0)
        
        # Reset filter values
        self.mod_wheel_value = 0.0
        self.expression_value = 0.0
        self.current_cutoff = self.default_cutoff
        
        # Update filter on all voices
        for _, voice_idx in self.active_notes.items():
            voice = self.voices[voice_idx]
            voice.set_param("cutoff", self.default_cutoff)
        
        LOG.info("Reset all controllers to defaults") 
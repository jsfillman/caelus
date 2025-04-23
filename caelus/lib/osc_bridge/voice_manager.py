"""
Voice allocation and management for polyphonic synth
"""
from lib.common.utils import LOG, midi_to_freq
from lib.osc_bridge.voice import Voice

class VoiceManager:
    """Manages allocation of voices for a polyphonic synth"""
    
    def __init__(self, voices):
        """Initialize with a list of Voice instances"""
        self.voices = voices
        self.active_notes = {}  # Maps MIDI note number to voice ID
        self.sustained_notes = set()  # Notes being sustained
        self.note_off_cache = {}  # Cache for note-off events while sustain is active
        self.sustain_active = False
        self.cc_values = {}  # Store CC values
        
        # Default controller values
        self.cc_defaults = {
            1: 0,  # Modulation wheel default (0)
        }
        
        # New attributes for filter cutoff control
        self.default_cutoff = 1000.0  # Default filter cutoff value
        self.current_cutoff = self.default_cutoff
        self.mod_wheel_value = 0.0
        self.expression_value = 0.0
        
        # Initialize pitch bend value
        self.pitch_bend = 0.0
        
        # Prepare voices
        for voice in self.voices:
            voice.reset()
            
        # No controllers to reset yet, so we don't call this immediately
        # It will be called when the router is fully set up
    
    def allocate_voice(self, note_num):
        """Allocate an available voice to a note number"""
        # Check if note is already playing
        if note_num in self.active_notes:
            voice_idx = self.active_notes[note_num]
            LOG.info(f"Note {note_num} already allocated to voice {voice_idx}, reusing")
            return self.voices[voice_idx]
        
        # Find available voice
        free_voice = None
        for i, voice in enumerate(self.voices):
            if not voice.is_active:
                free_voice = voice
                self.active_notes[note_num] = i
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
                if stolen_note in self.active_notes:
                    del self.active_notes[stolen_note]
                if stolen_note in self.sustained_notes:
                    self.sustained_notes.remove(stolen_note)
                if stolen_note in self.note_off_cache:
                    del self.note_off_cache[stolen_note]
                
                # Send multiple note-off commands to ensure it's really off
                oldest_voice.note_off()
                oldest_voice.send_osc("/gate", 0)
                oldest_voice.send_osc("/allNotesOff", 1)
            
            # Assign the voice to the new note
            self.active_notes[note_num] = oldest_voice_idx
            free_voice = oldest_voice
            
            # Double-check that the voice is properly marked as not active
            # This ensures it can be reactivated
            free_voice.is_active = False
        
        # Log voice allocation state
        LOG.debug(f"Voice allocation: {len(self.active_notes)} active notes, " +
                  f"{len(self.voices) - len([v for v in self.voices if v.is_active])} free voices")
        
        return free_voice
    
    def note_on(self, note_num, velocity):
        """Process note-on for a specific note number"""
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
    
    def note_off(self, note_num):
        """Turn off a note"""
        # Check if this note is active
        if note_num in self.active_notes:
            voice_idx = self.active_notes[note_num]
            
            # If sustain is active, cache the note-off but DO NOT remove from active_notes
            # This is the key fix - we need to keep track of notes in both places
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
    
    def _process_note_off(self, note, voice_idx):
        """Actually process a note-off event"""
        LOG.info(f"Turning off note {note} on voice {voice_idx}")
        
        # Get the voice
        if voice_idx >= len(self.voices):
            LOG.error(f"Voice index {voice_idx} out of range")
            return
            
        voice = self.voices[voice_idx]
        
        # Send note-off to the voice
        if voice:
            voice.note_off()
        
        # Remove from active notes if it's still there
        if note in self.active_notes:
            del self.active_notes[note]
        
        # Remove from sustained notes if it's there
        if note in self.sustained_notes:
            self.sustained_notes.remove(note)
            
        # Remove from note_off_cache if it's there
        if note in self.note_off_cache:
            del self.note_off_cache[note]
    
    def set_sustain(self, value):
        """Set the sustain pedal state"""
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
        
        # Send sustain pedal state to all voices
        for voice in self.voices:
            voice.set_sustain(1.0 if new_sustain_state else 0.0)
    
    def set_pitch_bend(self, value):
        """Set pitch bend value for all active voices"""
        self.pitch_bend = value
        
        # Update frequency for all active voices
        for note, voice_idx in self.active_notes.items():
            voice = self.voices[voice_idx]
            freq = midi_to_freq(note, self.pitch_bend)
            voice.send_osc("/freq", freq)
        
        LOG.info(f"Pitch bend: {value:.2f}")
        return True
        
    def all_notes_off(self):
        """Send note-off to all active voices"""
        for voice in self.voices:
            if voice.is_active:
                voice.note_off()
        
        self.active_notes.clear()
        self.sustained_notes.clear()
        self.note_off_cache.clear()
        return True
    
    def set_cc(self, cc_num, value):
        """Set a MIDI control change value"""
        # Store the CC value
        self.cc_values[cc_num] = value
        
        # Special handling for modulation wheel (CC1)
        if cc_num == 1:
            self.mod_wheel_value = value
            new_cutoff = self._update_filter_cutoff()
            LOG.info(f"Modulation wheel: {value:.2f} → filter cutoff updated to {new_cutoff}")
        
        # Special handling for expression pedal (CC11)
        elif cc_num == 11:
            self.expression_value = value
            new_cutoff = self._update_filter_cutoff()
            LOG.info(f"Expression pedal: {value:.2f} → filter cutoff updated to {new_cutoff}")
        
        # Send to all voices regardless
        for voice in self.voices:
            voice.set_cc(cc_num, value)
            
        # Apply current sustain value to all voices if this was the sustain pedal
        if cc_num == 64:
            # Sustain is CC64, normalize to 0-1 range
            self.set_sustain(value)
        
        LOG.info(f"Set CC {cc_num} to {value:.2f}")
        return True
    
    def _update_filter_cutoff(self):
        """Update filter cutoff based on modulation wheel and other controllers"""
        # Calculate filter cutoff based on modulation wheel
        # Modulation wheel reduces cutoff from default value down to 200Hz
        # (or some reasonable minimum for your synth)
        LOG.info(f"Updating filter cutoff with mod wheel: {self.mod_wheel_value:.2f}, expression: {self.expression_value:.2f}")
        
        # Start with default cutoff
        cutoff = self.default_cutoff
        
        # Apply modulation wheel (inverted - higher value = lower cutoff)
        # This creates a filter sweep effect controlled by mod wheel
        min_cutoff = 200.0  # 200 Hz is a reasonable minimum
        mod_range = self.default_cutoff - min_cutoff
        
        # Linear scaling with the modulation wheel
        cutoff = self.default_cutoff - (self.mod_wheel_value * mod_range)
        
        # Apply additional expression scaling if desired
        # (expression pedal is CC11)
        # This is just an example - you can customize this algorithm
        # expression_scaling = 1.0 + (self.expression_value * 0.5)  # Scale up to 50% extra
        # cutoff = cutoff * expression_scaling
        
        # Ensure cutoff stays in reasonable range
        cutoff = max(min_cutoff, min(20000.0, cutoff))
        
        LOG.info(f"Calculated new cutoff: {cutoff:.2f} Hz (default: {self.default_cutoff:.2f}, mod: {self.mod_wheel_value:.2f})")
        
        # Store the current cutoff
        last_cutoff = self.current_cutoff
        self.current_cutoff = cutoff
        
        # Only send messages if cutoff changed significantly
        if abs(cutoff - last_cutoff) > 0.1:
            # Apply to all active voices
            voice_count = 0
            for note, voice_idx in self.active_notes.items():
                if voice_idx < len(self.voices):
                    voice = self.voices[voice_idx]
                    if voice and voice.is_active:
                        LOG.info(f"Setting cutoff {cutoff:.2f} Hz on voice {voice_idx} (note {note})")
                        voice.send_osc("/cutoff", cutoff)
                        voice_count += 1
            
            # If there are no active voices, send to all voices
            if voice_count == 0:
                LOG.info(f"No active voices, setting cutoff {cutoff:.2f} Hz on all voices")
                for voice in self.voices:
                    voice.send_osc("/cutoff", cutoff)
                
        return cutoff

    def reset_all_controllers(self):
        """Reset and apply all controllers to all voices"""
        # Apply current filter cutoff state (if any)
        self._update_filter_cutoff()
        
        # Apply current sustain state to all voices
        for voice in self.voices:
            # Send sustain value to the synth
            voice.send_osc("/sustain", 1.0 if self.sustain_active else 0.0)
            LOG.debug(f"Initialized sustain for voice {voice.id} to {self.sustain_active}")
        
        return True 
import pyo
import time
import math
from oscillator import Oscillator

class PolyphonicVoice:
    def __init__(self, vol_sig, waveform_bank, nchnls, stability_cents=0):
        self.note_number = None
        self.velocity = None
        self.timestamp = 0
        
        # Create independent control signals
        self.freq_sig = pyo.Sig(440.0)
        self.amp_sig = pyo.Sig(0.0)
        
        # Create 8 oscillators for this voice
        self.oscillators = []
        for i in range(8):
            osc = Oscillator(
                self.freq_sig, self.amp_sig, vol_sig, 
                out_chnl=i % nchnls,  # Route to appropriate channel 
                waveform_bank=waveform_bank, 
                table_name="triangle"
            )
            self.oscillators.append(osc)
    
    def play_note(self, note, velocity, stability_cents=0):
        """Play a note on this voice"""
        # Update note info
        self.note_number = note
        self.velocity = velocity
        self.timestamp = time.time()
        
        # Set frequency and amplitude
        self.freq_sig.value = pyo.midiToHz(note)
        self.amp_sig.value = velocity / 127.0 * 0.2
        
        # Apply stability detuning
        detune_values = []
        if stability_cents > 0:
            for osc in self.oscillators:
                cents = osc.apply_stability_detune(stability_cents)
                detune_values.append(cents)
            print(f"Applied stability detuning (±{stability_cents:.2f} cents): {[f'{c:.2f}' for c in detune_values]}")
        
        # Start all oscillators
        for osc in self.oscillators:
            osc.env.play()
    
    def release_note(self):
        """Release the current note"""
        # Stop all oscillators
        for osc in self.oscillators:
            osc.env.stop()
        
        # Clear note info (allows voice to be reused)
        self.note_number = None
        self.velocity = None
    
    def is_active(self):
        """Check if voice is currently playing a note"""
        return self.note_number is not None

class VoiceManager:
    def __init__(self, max_voices, vol_sig, waveform_bank, stability_control, nchnls):
        self.max_voices = max_voices
        self.vol_sig = vol_sig
        self.waveform_bank = waveform_bank
        self.stability_control = stability_control
        self.nchnls = nchnls
        
        # Initialize voice pool
        self.voices = []
        for i in range(max_voices):
            voice = PolyphonicVoice(vol_sig, waveform_bank, nchnls)
            self.voices.append(voice)
        
        # Track active notes
        self.active_notes = {}  # note_number -> voice
        
        print(f"Voice manager initialized with {max_voices} voices")
    
    def note_on(self, note, velocity):
        """Start playing a note"""
        # If note is already playing, stop it first
        if note in self.active_notes:
            self.note_off(note)
        
        # Find a free voice, or steal the oldest one
        voice = self._find_voice()
        
        # Play the note
        voice.play_note(note, velocity, self.stability_control.value)
        
        # Track the active note
        self.active_notes[note] = voice
        
        # Adjust volume based on polyphony
        self._adjust_volume()
        
        # Log the active voice count
        active_count = sum(1 for v in self.voices if v.is_active())
        print(f"Note ON: {note}, velocity: {velocity}, active voices: {active_count}/{self.max_voices}")
    
    def note_off(self, note):
        """Stop playing a note"""
        if note in self.active_notes:
            # Release the voice
            self.active_notes[note].release_note()
            
            # Remove from active notes
            del self.active_notes[note]
            
            # Adjust volume based on remaining polyphony
            self._adjust_volume()
            
            # Log the active voice count
            active_count = sum(1 for v in self.voices if v.is_active())
            print(f"Note OFF: {note}, active voices: {active_count}/{self.max_voices}")
    
    def _find_voice(self):
        """Find an available voice or steal the oldest one"""
        # First, try to find an unused voice
        for voice in self.voices:
            if not voice.is_active():
                return voice
        
        # If all voices are active, steal the oldest one
        oldest_voice = min((v for v in self.voices if v.is_active()), 
                          key=lambda v: v.timestamp)
        
        print(f"All {self.max_voices} voices in use. Stealing voice from note {oldest_voice.note_number}")
        
        # Remove from active notes
        for note, voice in list(self.active_notes.items()):
            if voice == oldest_voice:
                del self.active_notes[note]
                break
        
        # Release the voice
        oldest_voice.release_note()
        
        return oldest_voice
    
    def _adjust_volume(self):
        """Adjust master volume based on number of active voices"""
        active_count = len(self.active_notes)
        
        if active_count <= 1:
            # Full volume for single note
            self.vol_sig.value = 0.8
        else:
            # Scale down using square root for better perceptual balance
            self.vol_sig.value = 0.8 / math.sqrt(active_count)
            
        print(f"Volume adjusted to {self.vol_sig.value:.2f} for {active_count} active voices")
    
    def all_notes_off(self):
        """Stop all active notes"""
        for note in list(self.active_notes.keys()):
            self.note_off(note) 
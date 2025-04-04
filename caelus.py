"""
Caelus - An advanced FM synthesis engine with pyo
Enhanced with:
1. Self-feedback capabilities for each operator
2. Multi-tap delay effects
3. Pan LFO for dynamic stereo movement

This module implements a modular FM synthesis architecture with multiple operators,
extensive modulation capabilities, and parameter ramping for timbral evolution.
The system supports MIDI input and provides a comprehensive GUI for all parameters.
"""

from pyo import *
import mido
import yaml
import os
from threading import Thread


class Oscillator:
    """
    A modular oscillator component that can function as either a carrier or modulator.
    
    Enhanced with:
    1. Self-feedback capability
    2. Multi-tap delay effects
    3. Pan LFO for dynamic stereo movement
    
    Each oscillator has independent control over frequency ratio, modulation index,
    envelopes, and parameter ramping for both frequency and amplitude.
    """
    
    def __init__(self, name, role="operator", ratio=1.0, index=1.0, freq_offset=0.0):
        """
        Initialize an oscillator with the specified parameters.
        
        Args:
            name: The display name of the oscillator
            role: Either "carrier" or "operator" (modulator)
            ratio: Frequency ratio relative to the fundamental pitch (e.g., 2.0 = one octave higher)
            index: Modulation depth/intensity - higher values create more complex timbres with more harmonics
            freq_offset: Fine tuning adjustment in Hz for precise frequency control
        """
        # Basic parameters
        self.name = name
        self.role = role
        self.freq_ratio = Sig(ratio)       # Frequency ratio relative to base pitch (e.g., 2.0 = one octave higher)
        self.freq_ratio_fine = Sig(0.0)    # Fine adjustment for frequency ratio
        self.mod_depth = Sig(index)        # Modulation depth/intensity - higher values create more harmonics
        self.mod_depth_fine = Sig(0.0)     # Fine adjustment for modulation depth
        self.tuning_offset = Sig(freq_offset)  # Fine tuning adjustment in Hz
        
        # Waveform
        self.table = HarmTable([1])  # Default to sine wave
        
        # ADSR envelopes
        self.freq_env = Adsr(attack=0.01, decay=0.1, sustain=0.5, release=0.3, dur=1, mul=50)
        
        # Use a lower multiplier for carrier to prevent clipping
        if role == "carrier":
            self.amp_env = Adsr(attack=0.01, decay=0.1, sustain=0.8, release=0.5, dur=1, mul=0.15)
        else:
            self.amp_env = Adsr(attack=0.01, decay=0.1, sustain=0.5, release=0.3, dur=1, mul=0.5)
        
        # Envelope delays
        self.freq_delay = Sig(0.0)
        self.depth_delay = Sig(0.0)
        
        # Frequency ramp parameters
        self.freq_ramp_start = Sig(0.0)
        self.freq_ramp_end = Sig(0.0)
        self.freq_ramp_time = Sig(1.0)       # Macro control for ramp time
        self.freq_ramp_time_fine = Sig(0.0)  # Fine adjustment for ramp time
        self.freq_ramp = Linseg([(0, self.freq_ramp_start.value), 
                                (self.freq_ramp_time.value, self.freq_ramp_end.value)])
        
        # Amplitude ramp parameters
        self.amp_ramp_start = Sig(1.0)
        self.amp_ramp_end = Sig(1.0)
        self.amp_ramp_time = Sig(1.0)        # Macro control for ramp time
        self.amp_ramp_time_fine = Sig(0.0)   # Fine adjustment for ramp time
        self.amp_ramp = Linseg([(0, self.amp_ramp_start.value), 
                               (self.amp_ramp_time.value, self.amp_ramp_end.value)])
        
        # Phase control
        self.phase = Sig(0.0)
        
        # === Feedback parameters ===
        self.feedback_amount = Sig(0.0)     # Amount of feedback (0-1)
        self.feedback_gain = Sig(0.5)        # Gain of feedback signal
        self.feedback_frequency = Sig(0.0)   # Frequency offset for feedback
        self.feedback_signal = None         # Will hold the feedback signal
        
        # === Multi-tap delay parameters ===
        self.delay_dry_wet = Sig(0.3)        # Mix between dry and wet signals (0-1)
        self.delay_time = [Sig(0.125), Sig(0.25), Sig(0.375)]  # Delay times for each tap in seconds
        self.delay_feedback = Sig(0.4)       # Feedback amount for the delay
        self.delay_signal = None            # Will hold the delayed signal
        
        # === NEW: LFO for panning parameters ===
        self.pan_lfo_active = Sig(0)        # 0 = off, 1 = on
        self.pan_lfo_freq = Sig(0.2)        # Default to 0.2 Hz (5 second cycle)
        self.pan_lfo_depth = Sig(0.5)       # Default to 0.5 depth (covers half the stereo field)
        self.pan_lfo_phase = Sig(0.0)       # Default to 0 phase
        self.pan_lfo_center = Sig(0.5)      # Default to center pan position
        
        # Create the LFO oscillator using HarmTable for efficiency
        self.pan_lfo_wave = HarmTable([1])  # Default to sine wave
        self.pan_lfo = Osc(table=self.pan_lfo_wave, freq=self.pan_lfo_freq, 
                          phase=self.pan_lfo_phase, mul=self.pan_lfo_depth)
        
        # Calculate panning position: center + LFO (when active)
        self.pan_calc = Clip(self.pan_lfo_center + (self.pan_lfo * self.pan_lfo_active), min=0, max=1)
        
        # The oscillator itself - will be properly connected in the synth class
        self.osc = None
        self.pre_osc = None  # Signal before feedback is applied
        self.freq = None
        self.amp = None
        self.base_freq = None
        self.output = None   # The final output signal after all processing
        
    def update_ramps(self):
        """
        Update ramp segments based on combined macro and fine parameter values.
        """
        # Calculate combined ramp times (ensure they never go below minimum)
        freq_time = max(0.001, self.freq_ramp_time.get() + self.freq_ramp_time_fine.get())
        amp_time = max(0.001, self.amp_ramp_time.get() + self.amp_ramp_time_fine.get())
        
        # Update frequency ramp
        self.freq_ramp.setList([
            (0, self.freq_ramp_start.get()),
            (freq_time, self.freq_ramp_end.get())
        ])
        
        # Update amplitude ramp
        self.amp_ramp.setList([
            (0, self.amp_ramp_start.get()),
            (amp_time, self.amp_ramp_end.get())
        ])
    
    def get_freq_ratio(self):
        """Get the combined frequency ratio from macro and fine controls"""
        return self.freq_ratio.get() + self.freq_ratio_fine.get()
    
    def get_mod_depth(self):
        """Get the combined modulation depth from macro and fine controls"""
        return self.mod_depth.get() + self.mod_depth_fine.get()
    
    def setup_feedback(self):
        """Set up the feedback path for the oscillator"""
        if self.osc is not None and self.feedback_amount.get() > 0:
            # Create a delayed version of our own output signal
            # This avoids zero-delay feedback which can cause computation issues
            delayed_feedback = Delay(self.osc, delay=0.001)
            
            # Scale the feedback signal by the feedback amount
            scaled_feedback = delayed_feedback * self.feedback_amount * self.feedback_gain
            
            # Apply frequency offset to feedback if needed
            if self.feedback_frequency.get() != 0:
                # Use an additional oscillator to create frequency shift in feedback
                feedback_pitch = self.base_freq + self.feedback_frequency
                feedback_osc = Sine(freq=feedback_pitch, mul=scaled_feedback)
                self.feedback_signal = feedback_osc
            else:
                self.feedback_signal = scaled_feedback
            
            # Apply the feedback to the frequency
            if hasattr(self, 'freq') and self.freq is not None:
                # Store original frequency signal
                self.pre_feedback_freq = self.freq
                
                # Add feedback to frequency
                self.freq = self.freq + self.feedback_signal
    
    def setup_delay(self):
        """Set up the multi-tap delay effects for the oscillator with LFO panning"""
        if self.osc is not None:
            # Create panner for the main oscillator with LFO control
            self.direct_panner = Pan(self.osc, outs=2, pan=self.pan_calc)
            
            # Create a multi-tap delay with three taps for rich stereo spread
            tap1 = Delay(self.osc, delay=self.delay_time[0], feedback=self.delay_feedback, mul=0.6)
            tap2 = Delay(self.osc, delay=self.delay_time[1], feedback=self.delay_feedback * 0.8, mul=0.4)
            tap3 = Delay(self.osc, delay=self.delay_time[2], feedback=self.delay_feedback * 0.6, mul=0.3)
            
            # Mix the three taps with offset pan positions based on the LFO position
            # This creates a wider stereo image
            tap1_pan = Pan(tap1, pan=Clip(self.pan_calc - 0.2, min=0, max=1))
            tap2_pan = Pan(tap2, pan=self.pan_calc)
            tap3_pan = Pan(tap3, pan=Clip(self.pan_calc + 0.2, min=0, max=1))
            
            # Mix the delayed signals
            self.delay_signal = Mix([tap1_pan, tap2_pan, tap3_pan], voices=2)
            
            # Create a dry/wet balance between original and delayed signal
            self.output = Interp(self.direct_panner, self.delay_signal, interp=self.delay_dry_wet)
        else:
            # If no oscillator is created yet, just set output to None
            self.output = None
    
    def play(self):
        """
        Trigger the oscillator, activating envelopes and ramps.
        
        Called when a note is played to start the sound generation process.
        """
        # Play envelopes with delays
        CallAfter(self.freq_env.play, self.freq_delay.value)
        CallAfter(self.amp_env.play, self.depth_delay.value)
        
        # Reset and play ramps
        self.freq_ramp.play()
        self.amp_ramp.play()
    
    def stop(self):
        """
        Release the oscillator by stopping its envelopes.
        
        Ramps complete on their own and don't need to be stopped.
        """
        CallAfter(self.freq_env.stop, self.freq_delay.value)
        CallAfter(self.amp_env.stop, self.depth_delay.value)
    
    def setup_gui(self):
        """
        Create GUI controls for all parameters of this oscillator with proper value ranges and scaling.
        """
        from pyo import SLMap
        
        # Frequency ratio - macro control (logarithmic scaling)
        freq_ratio_map = SLMap(0.1, 20.0, 'log', 'value', self.freq_ratio.get())
        self.freq_ratio.ctrl([freq_ratio_map], title=f"{self.name} Frequency Ratio")
        
        # Frequency ratio - fine tuning (±0.1 range, linear scaling)
        freq_ratio_fine_map = SLMap(-0.1, 0.1, 'lin', 'value', self.freq_ratio_fine.get())
        self.freq_ratio_fine.ctrl([freq_ratio_fine_map], title=f"{self.name} Freq Ratio Fine")
        
        # Modulation depth - macro control (logarithmic scaling)
        # Use 0.01 as minimum for log scale to avoid log(0) issues
        mod_depth_map = SLMap(0.01, 15.0, 'log', 'value', self.mod_depth.get())
        self.mod_depth.ctrl([mod_depth_map], title=f"{self.name} Modulation Depth")
        
        # Modulation depth - fine tuning (linear scaling)
        mod_depth_fine_map = SLMap(0.0, 2.0, 'lin', 'value', self.mod_depth_fine.get())
        self.mod_depth_fine.ctrl([mod_depth_fine_map], title=f"{self.name} Mod Depth Fine")
        
        # Fine tuning (linear mapping)
        tuning_map = SLMap(-100.0, 100.0, 'lin', 'value', self.tuning_offset.get())
        self.tuning_offset.ctrl([tuning_map], title=f"{self.name} Fine Tuning (Hz)")
        
        # Phase (linear mapping)
        phase_map = SLMap(0.0, 1.0, 'lin', 'value', self.phase.get())
        self.phase.ctrl([phase_map], title=f"{self.name} Phase")
        
        # For ADSR envelopes, use the built-in control panel
        # Do not attempt to create custom SLMap controls
        self.freq_env.ctrl(title=f"{self.name} Freq Env")
        self.amp_env.ctrl(title=f"{self.name} Amp Env")
        
        # Envelope delays (logarithmic mapping for better control of short times)
        # Use 0.001 as minimum for log scale to avoid log(0) issues
        freq_delay_map = SLMap(0.001, 2.0, 'log', 'value', self.freq_delay.get())
        self.freq_delay.ctrl([freq_delay_map], title=f"{self.name} Freq Delay (sec)")
        
        depth_delay_map = SLMap(0.001, 2.0, 'log', 'value', self.depth_delay.get())
        self.depth_delay.ctrl([depth_delay_map], title=f"{self.name} Depth Delay (sec)")
        
        # Frequency ramp parameters (linear mapping for start/end values)
        freq_ramp_start_map = SLMap(-12.0, 12.0, 'lin', 'value', self.freq_ramp_start.get())
        freq_ramp_end_map = SLMap(-12.0, 12.0, 'lin', 'value', self.freq_ramp_end.get())
        
        # Frequency ramp time - macro (up to 5 minutes, logarithmic for better control)
        freq_ramp_time_map = SLMap(0.1, 300.0, 'log', 'value', self.freq_ramp_time.get())
        
        # Frequency ramp time - fine (precise control for short ramps)
        freq_ramp_time_fine_map = SLMap(-0.099, 5.0, 'lin', 'value', self.freq_ramp_time_fine.get())
        
        self.freq_ramp_start.ctrl([freq_ramp_start_map], title=f"{self.name} Freq Ramp Start")
        self.freq_ramp_end.ctrl([freq_ramp_end_map], title=f"{self.name} Freq Ramp End")
        self.freq_ramp_time.ctrl([freq_ramp_time_map], title=f"{self.name} Freq Ramp Time")
        self.freq_ramp_time_fine.ctrl([freq_ramp_time_fine_map], title=f"{self.name} Freq Ramp Time Fine")
        
        # Amplitude ramp parameters (linear mapping for start/end values)
        # Use a minimum slightly above 0 for better log scaling
        amp_ramp_start_map = SLMap(0.01, 5.0, 'lin', 'value', self.amp_ramp_start.get())
        amp_ramp_end_map = SLMap(0.01, 5.0, 'lin', 'value', self.amp_ramp_end.get())
        
        # Amplitude ramp time - macro (up to 5 minutes, logarithmic for better control)
        amp_ramp_time_map = SLMap(0.1, 300.0, 'log', 'value', self.amp_ramp_time.get())
        
        # Amplitude ramp time - fine (precise control for short ramps)
        amp_ramp_time_fine_map = SLMap(-0.099, 5.0, 'lin', 'value', self.amp_ramp_time_fine.get())
        
        self.amp_ramp_start.ctrl([amp_ramp_start_map], title=f"{self.name} Amp Ramp Start")
        self.amp_ramp_end.ctrl([amp_ramp_end_map], title=f"{self.name} Amp Ramp End")
        self.amp_ramp_time.ctrl([amp_ramp_time_map], title=f"{self.name} Amp Ramp Time")
        self.amp_ramp_time_fine.ctrl([amp_ramp_time_fine_map], title=f"{self.name} Amp Ramp Time Fine")
        
        # === Feedback controls ===
        feedback_amount_map = SLMap(0.0, 1.0, 'lin', 'value', self.feedback_amount.get())
        self.feedback_amount.ctrl([feedback_amount_map], title=f"{self.name} Feedback Amount")
        
        feedback_gain_map = SLMap(0.0, 2.0, 'lin', 'value', self.feedback_gain.get())
        self.feedback_gain.ctrl([feedback_gain_map], title=f"{self.name} Feedback Gain")
        
        feedback_freq_map = SLMap(-200.0, 200.0, 'lin', 'value', self.feedback_frequency.get())
        self.feedback_frequency.ctrl([feedback_freq_map], title=f"{self.name} Feedback Freq Shift")
        
        # === Multi-tap delay controls ===
        delay_drywet_map = SLMap(0.0, 1.0, 'lin', 'value', self.delay_dry_wet.get())
        self.delay_dry_wet.ctrl([delay_drywet_map], title=f"{self.name} Delay Dry/Wet")
        
        # We'll use single controls for each tap time
        delay_time1_map = SLMap(0.01, 2.0, 'log', 'value', self.delay_time[0].get())
        delay_time2_map = SLMap(0.01, 2.0, 'log', 'value', self.delay_time[1].get())
        delay_time3_map = SLMap(0.01, 2.0, 'log', 'value', self.delay_time[2].get())
        
        self.delay_time[0].ctrl([delay_time1_map], title=f"{self.name} Delay Time 1")
        self.delay_time[1].ctrl([delay_time2_map], title=f"{self.name} Delay Time 2")
        self.delay_time[2].ctrl([delay_time3_map], title=f"{self.name} Delay Time 3")
        
        delay_feedback_map = SLMap(0.0, 0.99, 'lin', 'value', self.delay_feedback.get())
        self.delay_feedback.ctrl([delay_feedback_map], title=f"{self.name} Delay Feedback")
        
        # === NEW: Pan LFO controls ===
        pan_lfo_active_map = SLMap(0.0, 1.0, 'lin', 'value', self.pan_lfo_active.get())
        self.pan_lfo_active.ctrl([pan_lfo_active_map], title=f"{self.name} Pan LFO On/Off")
        
        pan_lfo_center_map = SLMap(0.0, 1.0, 'lin', 'value', self.pan_lfo_center.get())
        self.pan_lfo_center.ctrl([pan_lfo_center_map], title=f"{self.name} Pan Center")
        
        pan_lfo_freq_map = SLMap(0.01, 20.0, 'log', 'value', self.pan_lfo_freq.get())
        self.pan_lfo_freq.ctrl([pan_lfo_freq_map], title=f"{self.name} Pan LFO Rate")
        
        pan_lfo_depth_map = SLMap(0.0, 1.0, 'lin', 'value', self.pan_lfo_depth.get())
        self.pan_lfo_depth.ctrl([pan_lfo_depth_map], title=f"{self.name} Pan LFO Depth")
        
        pan_lfo_phase_map = SLMap(0.0, 1.0, 'lin', 'value', self.pan_lfo_phase.get())
        self.pan_lfo_phase.ctrl([pan_lfo_phase_map], title=f"{self.name} Pan LFO Phase")
 
    def get_parameters(self):
        """
        Return a dictionary with all parameters for saving to a preset file.
        
        Returns:
            dict: All oscillator parameters formatted for YAML serialization
        """
        params = {
            "ratio": self.freq_ratio.get(),
            "ratio_fine": self.freq_ratio_fine.get(),
            "index": self.mod_depth.get(),
            "index_fine": self.mod_depth_fine.get(),
            "freq_offset": self.tuning_offset.get(),
            "phase": self.phase.get(),
            
            "freq_env": {
                "attack": self.freq_env.attack,
                "decay": self.freq_env.decay,
                "sustain": self.freq_env.sustain,
                "release": self.freq_env.release,
                "mul": self.freq_env.mul
            },
            "amp_env": {
                "attack": self.amp_env.attack,
                "decay": self.amp_env.decay,
                "sustain": self.amp_env.sustain,
                "release": self.amp_env.release,
                "mul": self.amp_env.mul
            },
            
            "freq_delay": self.freq_delay.get(),
            "depth_delay": self.depth_delay.get(),
            
            "freq_ramp": {
                "start": self.freq_ramp_start.get(),
                "end": self.freq_ramp_end.get(),
                "time": self.freq_ramp_time.get(),
                "time_fine": self.freq_ramp_time_fine.get()
            },
            "amp_ramp": {
                "start": self.amp_ramp_start.get(),
                "end": self.amp_ramp_end.get(),
                "time": self.amp_ramp_time.get(),
                "time_fine": self.amp_ramp_time_fine.get()
            },
            
            # Feedback parameters
            "feedback": {
                "amount": self.feedback_amount.get(),
                "gain": self.feedback_gain.get(),
                "frequency": self.feedback_frequency.get()
            },
            
            # Delay parameters
            "delay": {
                "dry_wet": self.delay_dry_wet.get(),
                "time": [self.delay_time[0].get(), self.delay_time[1].get(), self.delay_time[2].get()],
                "feedback": self.delay_feedback.get()
            },
            
            # NEW: Pan LFO parameters
            "pan_lfo": {
                "active": self.pan_lfo_active.get(),
                "center": self.pan_lfo_center.get(),
                "freq": self.pan_lfo_freq.get(),
                "depth": self.pan_lfo_depth.get(),
                "phase": self.pan_lfo_phase.get()
            }
        }
        return params
        
    def load_parameters(self, params):
        """
        Load parameters from a dictionary (typically from a YAML preset file).
        
        Args:
            params: Dictionary containing oscillator parameters
        """
        # Basic parameters
        self.freq_ratio.value = params.get("ratio", 1.0)
        self.freq_ratio_fine.value = params.get("ratio_fine", 0.0)
        self.mod_depth.value = params.get("index", 1.0)
        self.mod_depth_fine.value = params.get("index_fine", 0.0)
        self.tuning_offset.value = params.get("freq_offset", 0.0)
        self.phase.value = params.get("phase", 0.0)
        
        # Envelope parameters
        freq_env_params = params.get("freq_env", {})
        self.freq_env.attack = freq_env_params.get("attack", 0.01)
        self.freq_env.decay = freq_env_params.get("decay", 0.1)
        self.freq_env.sustain = freq_env_params.get("sustain", 0.5)
        self.freq_env.release = freq_env_params.get("release", 0.3)
        self.freq_env.mul = freq_env_params.get("mul", 50)
        
        amp_env_params = params.get("amp_env", {})
        self.amp_env.attack = amp_env_params.get("attack", 0.01)
        self.amp_env.decay = amp_env_params.get("decay", 0.1)
        self.amp_env.sustain = amp_env_params.get("sustain", 0.5)
        self.amp_env.release = amp_env_params.get("release", 0.3)
        self.amp_env.mul = amp_env_params.get("mul", 0.5 if self.role != "carrier" else 0.15)
        
        # Delay parameters
        self.freq_delay.value = params.get("freq_delay", 0.0)
        self.depth_delay.value = params.get("depth_delay", 0.0)
        
        # Ramp parameters
        freq_ramp_params = params.get("freq_ramp", {})
        self.freq_ramp_start.value = freq_ramp_params.get("start", 0.0)
        self.freq_ramp_end.value = freq_ramp_params.get("end", 0.0)
        self.freq_ramp_time.value = freq_ramp_params.get("time", 1.0)
        self.freq_ramp_time_fine.value = freq_ramp_params.get("time_fine", 0.0)
        
        amp_ramp_params = params.get("amp_ramp", {})
        self.amp_ramp_start.value = amp_ramp_params.get("start", 1.0)
        self.amp_ramp_end.value = amp_ramp_params.get("end", 1.0)
        self.amp_ramp_time.value = amp_ramp_params.get("time", 1.0)
        self.amp_ramp_time_fine.value = amp_ramp_params.get("time_fine", 0.0)
        
        # Load feedback parameters
        feedback_params = params.get("feedback", {})
        self.feedback_amount.value = feedback_params.get("amount", 0.0)
        self.feedback_gain.value = feedback_params.get("gain", 0.5)
        self.feedback_frequency.value = feedback_params.get("frequency", 0.0)
        
        # Load delay parameters
        delay_params = params.get("delay", {})
        self.delay_dry_wet.value = delay_params.get("dry_wet", 0.3)
        
        delay_times = delay_params.get("time", [0.125, 0.25, 0.375])
        for i, time in enumerate(delay_times[:3]):  # Ensure we only take up to 3 values
            if i < len(self.delay_time):
                self.delay_time[i].value = time
                
        self.delay_feedback.value = delay_params.get("feedback", 0.4)
        
        # NEW: Load Pan LFO parameters
        pan_lfo_params = params.get("pan_lfo", {})
        self.pan_lfo_active.value = pan_lfo_params.get("active", 0.0)
        self.pan_lfo_center.value = pan_lfo_params.get("center", 0.5)
        self.pan_lfo_freq.value = pan_lfo_params.get("freq", 0.2)
        self.pan_lfo_depth.value = pan_lfo_params.get("depth", 0.5)
        self.pan_lfo_phase.value = pan_lfo_params.get("phase", 0.0)
        
        # Update the LFO oscillator with new parameters
        self.pan_lfo.freq = self.pan_lfo_freq
        self.pan_lfo.phase = self.pan_lfo_phase
        self.pan_lfo.mul = self.pan_lfo_depth
        
        # Update ramps with the new parameters
        self.update_ramps()


class Particle:
    """
    A single FM synthesis particle that manages multiple operators and audio routing.
    
    Enhanced with operator feedback, multitap delay effects, and pan LFO for rich, 
    evolving timbres with dynamic stereo movement.
    """
    
    def __init__(self, preset_file="caelus_preset.yaml", server=None):
        """
        Initialize the FM synthesis engine.
        
        Args:
            preset_file: Path to the YAML preset file to load (if exists)
            server: Existing pyo server or None to create a new one
        """
        # Store preset file path
        self.preset_file = preset_file
        
        # Use provided server or boot a new one
        if server:
            self.s = server
        else:
            self.s = Server(nchnls=2).boot()
            
        # === Control signals ===
        self.pitch = Sig(440.0)  # Base frequency
        self.velocity = Sig(0.0)  # MIDI velocity (0-1)
        self.aftertouch = Sig(0.0)  # MIDI aftertouch (0-1)
        
        # List to hold all operators (modulators)
        self.operators = []
        
        # Create carrier (always exists)
        self.carrier = Oscillator("Carrier", role="carrier", ratio=1.0, index=0.0)
        
        # Configure carrier defaults for ramps only (carrier ADSR is already set in Oscillator)
        self.carrier.amp_ramp_end.value = 0.8
        self.carrier.amp_ramp_time.value = 1.5
        
        # Add operator defaults (can be customized)
        self.operator_defaults = [
            # Each operator has default parameters that define its initial behavior
            {"name": "Op1", "ratio": 3.0, "index": 3.0, "amp_ramp_end": 0.5, "amp_ramp_time": 1.2,
             "env": {"attack": 0.005, "decay": 1.5, "sustain": 0.1, "release": 0.8}},
            {"name": "Op2", "ratio": 1.0, "index": 2.5, "amp_ramp_end": 0.7, "amp_ramp_time": 0.9,
             "env": {"attack": 0.01, "decay": 0.8, "sustain": 0.4, "release": 0.6}},
            {"name": "Op3", "ratio": 2.0, "index": 2.0, "amp_ramp_end": 0.6, "amp_ramp_time": 1.1,
             "env": {"attack": 0.02, "decay": 1.2, "sustain": 0.3, "release": 0.5}},
            {"name": "Op4", "ratio": 1.5, "index": 1.5, "amp_ramp_end": 0.4, "amp_ramp_time": 0.8,
             "env": {"attack": 0.01, "decay": 0.6, "sustain": 0.5, "release": 0.7}},
            {"name": "Op5", "ratio": 5.0, "index": 1.0, "amp_ramp_end": 0.3, "amp_ramp_time": 1.0,
             "env": {"attack": 0.015, "decay": 1.0, "sustain": 0.2, "release": 0.6}},
            {"name": "Op6", "ratio": 0.5, "index": 0.5, "amp_ramp_end": 0.2, "amp_ramp_time": 1.3,
             "env": {"attack": 0.025, "decay": 0.9, "sustain": 0.3, "release": 0.9}},
        ]
        
        # Initialize with a configurable number of operators
        self.initialize_operators(num_operators=6)
        
        # Try to load preset parameters if file exists
        self.load_preset()
        
        # Setup parameter change triggers
        self.setup_parameter_triggers()
        
        # Set up the FM chain and output
        self.setup_chain()
        
        # Set up GUI
        self.setup_gui()
        
        # Initialize active notes list for MIDI
        self.active_notes = []
        
        # Update ramps once to initialize
        self.update_all_ramps()
        
        # Register save function to run on exit
        import atexit
        atexit.register(self.save_preset)
        
        # If we created our own server, start it
        if not server:
            self.s.start()
            # Launch MIDI handler
            Thread(target=self.midi_loop, daemon=True).start()
    
    def initialize_operators(self, num_operators=4):
        """
        Initialize a specific number of operators with default values.
        
        Args:
            num_operators: Number of operators to create
        """
        self.operators = []
        
        # Create operators based on defaults or up to num_operators
        for i in range(min(num_operators, len(self.operator_defaults))):
            defaults = self.operator_defaults[i]
            op = Oscillator(
                defaults["name"], 
                role="modulator", 
                ratio=defaults["ratio"],  # Frequency ratio relative to base pitch
                index=defaults["index"]   # Modulation depth/intensity
            )
            
            # Set envelope parameters
            env = defaults["env"]
            op.freq_env = Adsr(
                attack=env["attack"], 
                decay=env["decay"], 
                sustain=env["sustain"], 
                release=env["release"], 
                dur=1, 
                mul=1.0
            )
            
            # Set ramp parameters
            op.amp_ramp_end.value = defaults["amp_ramp_end"]
            op.amp_ramp_time.value = defaults["amp_ramp_time"]
            
            # Add to operators list
            self.operators.append(op)
    
    def setup_parameter_triggers(self):
        """
        Set up triggers to update ramps when parameters change.
        
        This creates signal processing triggers that detect when parameters
        are changed through the GUI, ensuring ramps are properly updated.
        """
        # Build a sum of all parameters that should trigger updates
        trigger_sum = Sig(0)
        
        # Add operator parameters
        for op in self.operators:
            trigger_sum = trigger_sum + op.freq_ramp_start + op.freq_ramp_end + op.freq_ramp_time + \
                         op.amp_ramp_start + op.amp_ramp_end + op.amp_ramp_time
        
        # Add carrier parameters
        trigger_sum = trigger_sum + self.carrier.freq_ramp_start + self.carrier.freq_ramp_end + \
                     self.carrier.freq_ramp_time + self.carrier.amp_ramp_start + \
                     self.carrier.amp_ramp_end + self.carrier.amp_ramp_time
        
        # Create the trigger
        param_trigger = Change(trigger_sum).play()
        self.param_updater = TrigFunc(param_trigger, self.update_all_ramps)
    
    def on_server_close(self):
        """
        Save the preset when the server is closed.
        
        This ensures parameters are saved even if the application exits unexpectedly.
        """
        # Use a flag to prevent multiple calls
        if not hasattr(self, '_closing'):
            self._closing = True
            print("Saving preset...")
            self.save_preset()
        
    def save_preset(self):
        """
        Save all parameters to a preset file.
        
        Creates a YAML file containing all operator and carrier parameters.
        """
        preset_data = {"particle1": {}}
        
        # Save operator parameters
        for i, op in enumerate(self.operators):
            preset_data["particle1"][f"op{i+1}"] = op.get_parameters()
        
        # Save carrier parameters
        preset_data["particle1"]["carrier"] = self.carrier.get_parameters()
        
        try:
            with open(self.preset_file, 'w') as f:
                yaml.dump(preset_data, f, default_flow_style=False, sort_keys=False)
            print(f"Preset saved to {self.preset_file}")
        except Exception as e:
            print(f"Error saving preset: {e}")
    
    def load_preset(self):
        """
        Load parameters from a preset file if it exists.
        
        Looks for the specified preset file and loads its parameters.
        """
        if not os.path.exists(self.preset_file):
            print(f"No preset file found at {self.preset_file}, using defaults")
            return
        
        try:
            with open(self.preset_file, 'r') as f:
                preset_data = yaml.safe_load(f)
            
            # Load from the structure
            if "particle1" in preset_data:
                particle_data = preset_data["particle1"]
                
                # Load operator parameters
                for i, op in enumerate(self.operators):
                    key = f"op{i+1}"
                    if key in particle_data:
                        op.load_parameters(particle_data[key])
                        print(f"Loaded {key} parameters")
                
                # Load carrier parameters
                if "carrier" in particle_data:
                    self.carrier.load_parameters(particle_data["carrier"])
                    print("Loaded Carrier parameters")
            
            print(f"Preset loaded from {self.preset_file}")
        except Exception as e:
            print(f"Error loading preset: {e}")
    
    def update_all_ramps(self):
        """
        Update all operator and carrier ramps.
        
        Calls the update_ramps method on each oscillator to ensure
        all parameter changes are reflected in the audio processing.
        """
        for op in self.operators:
            op.update_ramps()
        self.carrier.update_ramps()
        
    def setup_chain(self):
        """
        Connect the operators in an FM chain with feedback, delay, and pan LFO.
        
        This method sets up the FM synthesis architecture with:
        1. Self-feedback on each oscillator
        2. Multi-tap delay effects
        3. Overall modulation strength control
        4. Pan LFO for dynamic stereo movement
        """
        # Create a GUI-controllable modulation gain factor using SLMap
        # Initialize with a moderate value of 1.0
        self.mod_gain = Sig(1.0)
        
        # Add GUI control for MOD_GAIN with a range from 0.1 to 5.0 using SLMap
        # This gives tremendous range from subtle to extreme FM
        from pyo import SLMap
        mod_gain_map = SLMap(0.1, 5.0, 'lin', 'value', 1.0)
        self.mod_gain.ctrl([mod_gain_map], title="FM Modulation Intensity")
        
        # Make sure we have operators
        if not self.operators:
            # No operators, carrier is unmodulated
            self.carrier.base_freq = self.pitch
            self.carrier.freq = self.carrier.base_freq + (self.carrier.freq_ramp * self.pitch)
            
            # Create carrier oscillator
            self.carrier.osc = Sine(
                freq=self.carrier.freq,
                mul=self.carrier.amp_env * self.velocity * (0.5 + self.aftertouch**2 * 2) * self.carrier.amp_ramp
            )
            
            # Apply feedback if enabled
            self.carrier.setup_feedback()
            
            # Apply delay and panning (with LFO)
            self.carrier.setup_delay()
            
            # Set output - either direct oscillator or delayed version
            if self.carrier.output is None:
                # Create panner for the oscillator with LFO control if no delay is used
                self.carrier.output = Pan(self.carrier.osc, outs=2, pan=self.carrier.pan_calc)
        else:
            # We'll implement a serial chain with user-controllable modulation strength
            
            # Start with the first operator (unmodulated except for self-feedback)
            # Use the combined frequency ratio (macro + fine)
            combined_ratio = self.operators[0].get_freq_ratio()
            combined_depth = self.operators[0].get_mod_depth()
            
            self.operators[0].base_freq = self.pitch * combined_ratio + self.operators[0].tuning_offset.get()
            self.operators[0].freq = self.operators[0].base_freq + (self.operators[0].freq_ramp * self.pitch)
            
            # Scale modulation depth by base frequency, with GUI control
            self.operators[0].amp = self.operators[0].base_freq * combined_depth * \
                                self.operators[0].amp_env * self.operators[0].amp_ramp * self.mod_gain
            
            # Create the oscillator
            self.operators[0].osc = Sine(
                freq=self.operators[0].freq, 
                phase=self.operators[0].phase, 
                mul=self.operators[0].amp
            )
            
            # Add feedback loop to first operator
            self.operators[0].setup_feedback()
            
            # Add delay and panning with LFO to first operator
            self.operators[0].setup_delay()
            
            # Now set up the rest of the operators, each modulated by the previous one
            for i in range(1, len(self.operators)):
                prev_op = self.operators[i-1]
                curr_op = self.operators[i]
                
                # Get combined ratio and depth for this operator
                combined_ratio = curr_op.get_freq_ratio()
                combined_depth = curr_op.get_mod_depth()
                
                # Calculate base frequency (without modulation)
                curr_op.base_freq = self.pitch * combined_ratio + curr_op.tuning_offset.get()
                
                # Apply modulation with GUI-controllable strength
                # Use output from previous operator which includes any delay and feedback
                mod_signal = (prev_op.output if prev_op.output is not None else prev_op.osc) * \
                             (1.0 + combined_depth) * self.mod_gain
                
                # Apply frequency modulation from previous operator
                curr_op.freq = curr_op.base_freq + (curr_op.freq_ramp * self.pitch) + mod_signal
                
                # Scale modulation depth by base frequency with GUI-controllable strength
                curr_op.amp = curr_op.base_freq * combined_depth * 1.5 * \
                            curr_op.amp_env * curr_op.amp_ramp * self.mod_gain
                
                # Create oscillator
                curr_op.osc = Sine(freq=curr_op.freq, phase=curr_op.phase, mul=curr_op.amp)
                
                # Add feedback loop to this operator
                curr_op.setup_feedback()
                
                # Add delay and panning with LFO to this operator
                curr_op.setup_delay()
                
                # Debug output
                print(f"{curr_op.name}: Base freq = {curr_op.base_freq.get()}, Modulated by {prev_op.name}")
            
            # Carrier is modulated by the last operator with GUI-controllable strength
            last_op = self.operators[-1]
            combined_ratio = self.carrier.get_freq_ratio()
            
            self.carrier.base_freq = self.pitch * combined_ratio + self.carrier.tuning_offset.get()
            
            # Apply modulation to carrier, with extra emphasis but still GUI-controllable 
            # Use output from last operator which includes any delay and feedback
            mod_signal = (last_op.output if last_op.output is not None else last_op.osc) * self.mod_gain * 2.0
            self.carrier.freq = self.carrier.base_freq + (self.carrier.freq_ramp * self.pitch) + mod_signal
            
            # Debug output
            print(f"Carrier: Base freq = {self.carrier.base_freq.get()}, Modulated by {last_op.name}")
        
        # Carrier oscillator with amplitude controls
        self.carrier.osc = Sine(
            freq=self.carrier.freq,
            phase=self.carrier.phase,
            mul=self.carrier.amp_env * self.velocity * (0.5 + self.aftertouch**2 * 2) * self.carrier.amp_ramp
        )
        
        # Apply feedback to carrier
        self.carrier.setup_feedback()
        
        # Apply delay and panning with LFO to carrier
        self.carrier.setup_delay()
        
        # === STEREO OUTPUT WITH LFO PANNING ===
        # Use the carrier's processed output if available, otherwise use the raw oscillator with direct panning
        carrier_signal = self.carrier.output
        if carrier_signal is None:
            carrier_signal = Pan(self.carrier.osc, outs=2, pan=self.carrier.pan_calc)
        
        # === AUDIO OUTPUT WITH LIMITER ===
        # Dynamic limiting to handle modulation extremes
        self.limiter = Compress(
            input=carrier_signal,
            thresh=-18,
            ratio=25,
            risetime=0.001,
            falltime=0.07,
            lookahead=3,
            knee=0.4,
            outputAmp=False
        )
        
        # Final output level
        self.final = self.limiter * 0.6
        self.final.out()
    
    def play_note(self, note, velocity_val):
        """
        Play a note with the given velocity.
        
        Args:
            note: MIDI note number (0-127)
            velocity_val: MIDI velocity (0-127)
        """
        # Convert MIDI note to frequency (A4 = 69 = 440Hz)
        freq_val = 440.0 * (2 ** ((note - 69) / 12))
        self.pitch.value = freq_val
        self.velocity.value = velocity_val / 127
        
        # Play carrier envelope
        self.carrier.amp_env.play()
        
        # Play all operator envelopes
        for op in self.operators:
            op.freq_env.play()
            op.amp_env.play()
        
        # Force an update of the ramps
        self.update_all_ramps()
        
        # Play carrier ramps
        self.carrier.freq_ramp.play()
        self.carrier.amp_ramp.play()
        
        # Play all operator ramps
        for op in self.operators:
            op.freq_ramp.play()
            op.amp_ramp.play()
    
    def stop_note(self):
        """
        Stop the current note by releasing all envelopes.
        """
        # Stop carrier envelope
        self.carrier.amp_env.stop()
        
        # Stop all operator envelopes
        for op in self.operators:
            op.freq_env.stop()
            op.amp_env.stop()
    
    def midi_loop(self):
        """
        Handle MIDI input in a separate thread.
        
        This method runs in a separate thread and processes incoming MIDI messages,
        triggering notes and handling polyphony by tracking active notes.
        """
        # Try to find a MIDI device
        port_name = None
        for name in mido.get_input_names():
            print("→", name)
            if "Xkey" in name:
                port_name = name
                break
        if not port_name:
            print("❌ Xkey not found. Using default.")
            port_name = mido.get_input_names()[0]
        
        print(f"🎹 Listening on: {port_name}")
        
        # Open the MIDI port and process messages
        with mido.open_input(port_name) as port:
            for msg in port:
                if msg.type == 'note_on' and msg.velocity > 0:
                    # Add the new note to our active notes list
                    if msg.note not in self.active_notes:
                        self.active_notes.append(msg.note)
                    
                    # Play the most recently pressed note (last in the list)
                    self.play_note(self.active_notes[-1], msg.velocity)
                    
                elif msg.type in ['note_off', 'note_on'] and msg.velocity == 0:
                    # Remove the note from active notes
                    if msg.note in self.active_notes:
                        self.active_notes.remove(msg.note)
                    
                    # If we still have active notes, play the most recent one
                    if self.active_notes:
                        # Get the last pressed note still active
                        last_note = self.active_notes[-1]
                        self.play_note(last_note, 100)  # Use default velocity of 100
                    else:
                        # No notes left, stop sound
                        self.stop_note()
                        
                elif msg.type == 'polytouch':
                    # Apply aftertouch only if it's for the currently playing note
                    if self.active_notes and msg.note == self.active_notes[-1]:
                        self.aftertouch.value = msg.value / 127
    
    def setup_gui(self):
        """
        Set up the GUI controls for all oscillators.
        """
        # Set up GUI for each operator
        for op in self.operators:
            op.setup_gui()
        
        # Set up carrier GUI
        self.carrier.setup_gui()


class CaelusSynth:
    """
    Top-level FM synthesis engine that manages multiple particles.
    
    This class acts as a container for multiple Particle instances, allowing for
    more complex sound design through layering of multiple FM synthesis voices.
    """
    
    def __init__(self, num_particles=1, preset_dir="presets"):
        """
        Initialize the Caelus FM synthesis engine.
        
        Args:
            num_particles: Number of FM synthesis particles to create
            preset_dir: Directory for preset files
        """
        # Boot the audio server
        self.s = Server(nchnls=2).boot()
        self.s.start()
        
        # Create preset directory if it doesn't exist
        if not os.path.exists(preset_dir):
            os.makedirs(preset_dir)
        
        # List to store particles
        self.particles = []
        
        # Create particles
        for i in range(num_particles):
            preset_file = os.path.join(preset_dir, f"particle{i+1}.yaml")
            particle = Particle(preset_file=preset_file, server=self.s)
            self.particles.append(particle)
        
        # Track active notes across all particles
        self.active_notes = []
        
        # Start MIDI handler
        Thread(target=self.midi_loop, daemon=True).start()
    
    def midi_loop(self):
        """
        Handle MIDI input and distribute to all particles.
        """
        # Try to find a MIDI device
        port_name = None
        for name in mido.get_input_names():
            print("→", name)
            if "Xkey" in name:
                port_name = name
                break
        if not port_name:
            print("❌ Xkey not found. Using default.")
            port_name = mido.get_input_names()[0]
        
        print(f"🎹 Listening on: {port_name}")
        
        # Open the MIDI port and process messages
        with mido.open_input(port_name) as port:
            for msg in port:
                if msg.type == 'note_on' and msg.velocity > 0:
                    # Add the new note to active notes list
                    if msg.note not in self.active_notes:
                        self.active_notes.append(msg.note)
                    
                    # Play the note on all particles
                    for particle in self.particles:
                        particle.play_note(msg.note, msg.velocity)
                    
                elif msg.type in ['note_off', 'note_on'] and msg.velocity == 0:
                    # Remove the note from active notes
                    if msg.note in self.active_notes:
                        self.active_notes.remove(msg.note)
                    
                    # If we still have active notes, play the most recent one on all particles
                    if self.active_notes:
                        last_note = self.active_notes[-1]
                        for particle in self.particles:
                            particle.play_note(last_note, 100)  # Default velocity
                    else:
                        # No notes left, stop sound on all particles
                        for particle in self.particles:
                            particle.stop_note()
                            
                elif msg.type == 'polytouch':
                    # Apply aftertouch to all particles if it's for the currently playing note
                    if self.active_notes and msg.note == self.active_notes[-1]:
                        for particle in self.particles:
                            particle.aftertouch.value = msg.value / 127
    
    def setup_gui(self):
        """
        Set up the GUI for the entire synth.
        """
        # Each particle has its own GUI controls already
        pass


# Example preset that includes pan LFO settings
default_preset = """
particle1:
  op1:
    ratio: 3.0
    index: 3.0
    freq_offset: 0.0
    phase: 0.0
    freq_env:
      attack: 0.005
      decay: 1.5
      sustain: 0.1
      release: 0.8
      mul: 1.0
    amp_env:
      attack: 0.001
      decay: 0.1
      sustain: 0.7
      release: 0.5
      mul: 1.0
    freq_delay: 0.0
    depth_delay: 0.0
    freq_ramp:
      start: 0.0
      end: 0.0
      time: 1.0
    amp_ramp:
      start: 1.0
      end: 0.5
      time: 1.2
    feedback:
      amount: 0.3
      gain: 0.7
      frequency: 20.0
    delay:
      dry_wet: 0.2
      time: [0.12, 0.24, 0.36]
      feedback: 0.3
    pan_lfo:
      active: 1.0
      center: 0.5
      freq: 0.2
      depth: 0.5
      phase: 0.0
  op2:
    ratio: 1.0
    index: 2.5
    freq_offset: 0.0
    phase: 0.25
    freq_env:
      attack: 0.01
      decay: 0.8
      sustain: 0.4
      release: 0.6
      mul: 1.0
    amp_env:
      attack: 0.001
      decay: 0.2
      sustain: 0.6
      release: 0.4
      mul: 0.8
    freq_delay: 0.01
    depth_delay: 0.01
    freq_ramp:
      start: 0.0
      end: 0.0
      time: 1.0
    amp_ramp:
      start: 1.0
      end: 0.7
      time: 0.9
    feedback:
      amount: 0.4
      gain: 0.5
      frequency: -15.0
    delay:
      dry_wet: 0.15
      time: [0.08, 0.16, 0.24]
      feedback: 0.4
    pan_lfo:
      active: 1.0
      center: 0.3
      freq: 0.15
      depth: 0.4
      phase: 0.5
  carrier:
    ratio: 1.0
    index: 0.0
    freq_offset: 0.0
    phase: 0.0
    freq_env:
      attack: 0.01
      decay: 0.1
      sustain: 0.8
      release: 0.5
      mul: 1.0
    amp_env:
      attack: 0.01
      decay: 0.1
      sustain: 0.8
      release: 0.5
      mul: 0.15
    freq_delay: 0.0
    depth_delay: 0.0
    freq_ramp:
      start: 0.0
      end: 0.0
      time: 1.5
    amp_ramp:
      start: 1.0
      end: 0.8
      time: 1.5
    feedback:
      amount: 0.2
      gain: 0.6
      frequency: 0.0
    delay:
      dry_wet: 0.35
      time: [0.25, 0.5, 0.75]
      feedback: 0.5
    pan_lfo:" \
    """
# Run the synthesizer
if __name__ == "__main__":
    # Create presets directory if it doesn't exist
    if not os.path.exists("presets"):
        os.makedirs("presets")
    
    # Create default preset file if it doesn't exist
    default_preset_path = "presets/default_pan_lfo.yaml"
    if not os.path.exists(default_preset_path):
        with open(default_preset_path, "w") as f:
            f.write(default_preset)
        print(f"Created default preset at {default_preset_path}")
    
    # Initialize with just one particle and the default pan LFO preset
    synth = Particle(preset_file=default_preset_path)
    synth.s.gui(locals())
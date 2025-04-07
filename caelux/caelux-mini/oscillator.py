import pyo
import random
from wavetables import WaveformBank

class Oscillator:
    """
    Class to manage a single oscillator in the Caelux Mini synthesizer.
    Each oscillator has identical capabilities, but can be used as a carrier or operator.
    """
    
    def __init__(self, server=None, name="OSC1", osc_type="carrier"):
        """Initialize the oscillator with server reference and type"""
        self.server = server
        self.name = name
        self.osc_type = osc_type  # "carrier" or "operator"
        
        # Initialize only if server is provided and running
        if self.server and self.server.getIsStarted():
            self.initialize()
        else:
            self.initialized = False
    
    def initialize(self):
        """Initialize all synthesis components"""
        if not self.server or not self.server.getIsStarted():
            self.initialized = False
            return False
            
        # Initialize wavetable bank
        self.wave_bank = WaveformBank(self.server)
        self.wave_bank.create_standard_tables()
        
        # State variables
        self.current_pitch_bend = 0.0
        self.current_note = None
        
        # Amp control: ramp → ADSR
        self.amp_ramp = pyo.Linseg([(0, 0), (1, 1)], loop=False)
        self.amp_env = pyo.Adsr(attack=0.01, decay=0.1, sustain=0.7, release=0.5, dur=0, mul=self.amp_ramp)

        # Freq control: ADSR (in Hz) + Linseg glide
        self.freq_adsr = pyo.Adsr(attack=0.01, decay=0.1, sustain=1.0, release=0.5, dur=0, mul=0)
        self.freq_linseg = pyo.Linseg([(0, 440), (1, 440)], loop=False)
        self.final_freq = self.freq_linseg + self.freq_adsr

        # Default parameters for oscillator bank
        self.modulated_freq = self.final_freq
        self.num_oscillators = 8
        self.detune = 0.001
        self.table_name = "sine"

        # Create initial base frequencies for oscillator bank
        self.base_freqs = []
        for i in range(self.num_oscillators):
            detune_factor = 1.0 + (self.detune * (i - (self.num_oscillators//2)))
            self.base_freqs.append(self.modulated_freq * detune_factor)

        # Create the oscillator bank
        self.osc = pyo.OscBank(
            table=self.wave_bank.get_table(self.table_name),
            freq=self.base_freqs,
            spread=0.1,
            num=self.num_oscillators,
            mul=self.amp_env
        )

        # Filter
        self.filter_ramp = pyo.Linseg([(0, 100), (1, 5000)], loop=False)
        self.moog_filter = pyo.MoogLP(self.osc, freq=self.filter_ramp, res=0.3)

        # Delay
        self.left_delay = pyo.Delay(self.moog_filter, delay=[0.15, 0.35, 0.55], feedback=0.3, mul=0.3)
        self.right_delay = pyo.Delay(self.moog_filter, delay=[0.2, 0.4, 0.6], feedback=0.3, mul=0.3)
        
        # Output panning
        self.l_pan = pyo.Pan(self.left_delay, outs=2, pan=0.0)
        self.r_pan = pyo.Pan(self.right_delay, outs=2, pan=1.0)
        self.stereo = self.l_pan + self.r_pan
        
        # Only output directly if carrier - operators will connect to modulation inputs
        if self.osc_type == "carrier":
            self.stereo.out()
        
        # Output for modulation when used as an operator
        if self.osc_type == "operator":
            # Get the raw signal from the left channel before any panning
            # This gives a stronger modulation signal directly from the oscillator
            self.mod_output = self.left_delay
        else:
            self.mod_output = None
        
        self.initialized = True
        return True
    
    def note_on(self, note, velocity, gui):
        """Handle a MIDI note-on event with current GUI parameters"""
        if not self.initialized:
            return
            
        # Base frequency calculation based on mode
        if gui.freq_mode.currentText() == "Manual":
            base = gui.manual_freq.itemAt(1).widget().value()
        else:
            base = pyo.midiToHz(note)
            
        # Apply detune (both coarse and fine)
        coarse_detune = gui.coarse_detune.itemAt(1).widget().value()
        fine_detune = gui.fine_detune.itemAt(1).widget().value() / 100.0  # Convert cents to semitones
        detune_factor = 2 ** ((coarse_detune + fine_detune) / 12.0)
        base *= detune_factor

        # Apply pitch bend
        bend_ratio = 2 ** (self.current_pitch_bend / 12.0)
        base *= bend_ratio
        
        # Now configure the oscillator bank
        wave_type = gui.wave_type.currentText()
        num_oscs = int(gui.num_oscs.itemAt(1).widget().value())
        detune_val = gui.detune.itemAt(1).widget().value()
        spread_val = gui.spread.itemAt(1).widget().value()
        phase_spread = gui.phase_spread.itemAt(1).widget().value()
        amp_distribution = gui.amp_dist.currentText()
        
        # Calculate frequencies based on detune mode
        detune_mode = gui.detune_mode.currentText()
        base_freqs = []
        base_amps = []
        
        for i in range(num_oscs):
            # Calculate detune factor based on selected mode
            if detune_mode == "Linear":
                # Linear detune spread around center frequency
                detune_factor = 1.0 + detune_val * (i - (num_oscs - 1) / 2.0) / ((num_oscs - 1) / 2.0)
            elif detune_mode == "Exponential":
                # Exponential spreading (more natural sounding)
                detune_factor = pow(2, detune_val * (i - (num_oscs - 1) / 2.0) / 12.0)
            else:  # Random
                # Random detuning within range
                detune_factor = 1.0 + detune_val * (random.random() * 2 - 1)
            
            base_freqs.append(base * detune_factor)
            
            # Calculate amplitude based on distribution
            if amp_distribution == "Equal":
                amp = 1.0 / num_oscs
            elif amp_distribution == "Decreasing":
                amp = 1.0 - (i / num_oscs)
            elif amp_distribution == "Increasing":
                amp = i / (num_oscs - 1) if num_oscs > 1 else 1.0
            elif amp_distribution == "Triangle":
                amp = 1.0 - abs(2.0 * i / (num_oscs - 1) - 1.0) if num_oscs > 1 else 1.0
            else:  # Bell curve
                mid = (num_oscs - 1) / 2
                amp = 1.0 - 0.8 * ((i - mid) / mid) ** 2 if num_oscs > 1 else 1.0
            
            base_amps.append(amp)
        
        # Normalize amplitudes
        amp_sum = sum(base_amps)
        if amp_sum > 0:
            base_amps = [a / amp_sum for a in base_amps]
        
        # Update the oscillator bank
        # First, get the current table
        current_table = self.wave_bank.get_table(wave_type)
        
        # Create a list of phase offsets based on the phase spread
        phases = []
        for i in range(num_oscs):
            if phase_spread > 0:
                phases.append((i / num_oscs) * phase_spread)
            else:
                phases.append(0)
        
        # Now update the oscillator
        self.osc.table = current_table
        self.osc.freq = base_freqs
        self.osc.spread = spread_val
        self.osc.mul = [self.amp_env * amp for amp in base_amps]
        self.osc.phase = phases

        # Get parameters from GUI for frequency
        start_rand = gui.start_rand.itemAt(1).widget().value()
        start_slew = gui.start_slew.itemAt(1).widget().value()
        end_slew = gui.end_slew.itemAt(1).widget().value()
        slew_time = gui.slew_time.itemAt(1).widget().value()
        slew_delay = gui.slew_delay.itemAt(1).widget().value()

        # Configure frequency ADSR
        self.freq_adsr.setAttack(gui.freq_attack.itemAt(1).widget().value())
        self.freq_adsr.setDecay(gui.freq_decay.itemAt(1).widget().value())
        self.freq_adsr.setSustain(gui.freq_sustain.itemAt(1).widget().value())
        self.freq_adsr.setRelease(gui.freq_release.itemAt(1).widget().value())
        
        # Set frequency envelope depth/intensity
        freq_env_depth = gui.freq_env_depth.itemAt(1).widget().value()
        self.freq_adsr.mul = freq_env_depth
        
        # Calculate frequencies with randomization
        freq_start = base + start_slew + random.uniform(-start_rand, start_rand)
        freq_end = base + end_slew
        
        # Set up the Linseg with delay before ramping
        if slew_delay > 0:
            self.freq_linseg.list = [(0, freq_start), (slew_delay, freq_start), 
                                     (slew_delay + slew_time, freq_end)]
        else:
            self.freq_linseg.list = [(0, freq_start), (slew_time, freq_end)]
            
        self.freq_linseg.play()
        self.freq_adsr.play()

        # Get amplitude ramp parameters including the new delay
        amp_start = gui.amp_ramp_start.itemAt(1).widget().value()
        amp_end = gui.amp_ramp_end.itemAt(1).widget().value()
        amp_time = gui.amp_ramp_time.itemAt(1).widget().value()
        amp_delay = gui.amp_ramp_delay.itemAt(1).widget().value()
        
        # Set up amplitude ramp with delay
        if amp_delay > 0:
            self.amp_ramp.list = [(0, amp_start), (amp_delay, amp_start), 
                                 (amp_delay + amp_time, amp_end)]
        else:
            self.amp_ramp.list = [(0, amp_start), (amp_time, amp_end)]
            
        self.amp_ramp.play()

        # Configure filter parameters
        filter_res = gui.filter_res.itemAt(1).widget().value()
        
        # Get filter ramp parameters
        filter_start = gui.filter_ramp_start.itemAt(1).widget().value()
        filter_end = gui.filter_ramp_end.itemAt(1).widget().value()
        filter_time = gui.filter_ramp_time.itemAt(1).widget().value()
        filter_delay = gui.filter_ramp_delay.itemAt(1).widget().value()
        
        # Set up filter ramp with delay
        if filter_delay > 0:
            self.filter_ramp.list = [(0, filter_start), (filter_delay, filter_start), 
                                    (filter_delay + filter_time, filter_end)]
        else:
            self.filter_ramp.list = [(0, filter_start), (filter_time, filter_end)]
            
        self.filter_ramp.play()
        
        # Update the filter resonance
        self.moog_filter.res = filter_res

        # Feedback routing
        source = gui.feedback_source.currentText()
        depth = gui.feedback_depth.itemAt(1).widget().value()

        if source == "Pre-Delay":
            feedback_signal = self.moog_filter  # Use the filter output
        elif source == "Post-Delay":
            feedback_signal = pyo.Mix(self.stereo, voices=1)
        else:
            feedback_signal = pyo.Sig(0)

        self.modulated_freq = self.final_freq + (feedback_signal * depth)
        self.osc.freq = self.modulated_freq

        # Amplitude envelope
        self.amp_env.setAttack(gui.amp_attack.itemAt(1).widget().value())
        self.amp_env.setDecay(gui.amp_decay.itemAt(1).widget().value())
        self.amp_env.setSustain(gui.amp_sustain.itemAt(1).widget().value())
        self.amp_env.setRelease(gui.amp_release.itemAt(1).widget().value())
        self.amp_env.play()

        # Delay update
        self.left_delay.delay = self._get_delays(gui.left_delays)
        self.right_delay.delay = self._get_delays(gui.right_delays)
        self.left_delay.feedback = gui.left_feedback.itemAt(1).widget().value()
        self.right_delay.feedback = gui.right_feedback.itemAt(1).widget().value()

        self.current_note = note
    
    def _get_delays(self, slider_list):
        """Helper to get delay times from sliders"""
        return [slider.itemAt(1).widget().value() for slider in slider_list]
    
    def note_off(self, note):
        """Handle a MIDI note-off event"""
        if not self.initialized:
            return
            
        if note == self.current_note:
            self.amp_env.stop()
            self.freq_adsr.stop()
            self.current_note = None
    
    def pitch_bend(self, value):
        """Handle pitch bend with a normalized value (-1 to 1)"""
        if not self.initialized:
            return
            
        self.current_pitch_bend = value * 2  # 2 semitone range
    
    def apply_modulation(self, mod_signal, amount=1.0):
        """Apply modulation from another oscillator to this one's frequency"""
        if not self.initialized:
            return
        
        # Create a scaled version of the modulation signal
        scaled_mod = mod_signal * amount
        
        # Apply it to the modulated frequency
        self.modulated_freq = self.final_freq + scaled_mod
        self.osc.freq = self.modulated_freq
        
        # Store reference to the modulation signal to prevent garbage collection
        self._mod_signal = scaled_mod
    
    def get_mod_output(self):
        """Get the modulation output signal (for operators)"""
        if self.osc_type == "operator" and self.initialized:
            return self.mod_output
        return None
    
    def shutdown(self):
        """Clean shutdown of audio components"""
        if not self.initialized:
            return
            
        # Stop any active sounds
        self.amp_env.stop()
        self.freq_adsr.stop()
        
        # Clear references to help with garbage collection
        self.stereo.stop()
        self.stereo = None
        self.l_pan = None
        self.r_pan = None
        self.left_delay = None
        self.right_delay = None
        self.moog_filter = None
        self.osc = None
        self.amp_env = None
        self.freq_adsr = None
        self.freq_linseg = None
        self.amp_ramp = None
        
        self.initialized = False
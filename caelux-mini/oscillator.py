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
        self.initialized = False  # Set initialized flag to False initially
        self.server = server
        self.name = name
        self.osc_type = osc_type  # "carrier" or "operator"
        
        # Bypass flags for each section
        self.osc_bypass = False
        self.freq_bypass = False
        self.amp_bypass = False
        self.filter_bypass = False
        self.delay_bypass = False
        
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

        # Filter with bypass capability
        self.filter_ramp = pyo.Linseg([(0, 100), (1, 5000)], loop=False)
        self.moog_filter = pyo.MoogLP(self.osc, freq=self.filter_ramp, res=0.3)
        # Selector for filter bypass
        self.filter_selector = pyo.Selector([self.osc, self.moog_filter], voice=1)

        # Delay with bypass capability
        self.left_delay = pyo.Delay(self.filter_selector, delay=[0.15, 0.35, 0.55], feedback=0.3, mul=0.3)
        self.right_delay = pyo.Delay(self.filter_selector, delay=[0.2, 0.4, 0.6], feedback=0.3, mul=0.3)
        # Selectors for delay bypass
        self.left_delay_selector = pyo.Selector([self.filter_selector, self.left_delay], voice=1)
        self.right_delay_selector = pyo.Selector([self.filter_selector, self.right_delay], voice=1)
        
        # Simplified stereo panner implementation
        # Create mono signals from left and right
        self.mono_left = pyo.Mix(self.left_delay_selector, voices=1)
        self.mono_right = pyo.Mix(self.right_delay_selector, voices=1)
        
        # Default stereo width (0=mono, 1=full stereo)
        self.stereo_width = 1.0
        
        # LFO for autopanning (Sine wave by default, 0-1 range)
        self.pan_lfo = pyo.Sine(freq=0.2, mul=0.5, add=0.5)
        self.use_autopan = False  # Default to manual panning
        
        # Pan position (default center)
        self.pan_pos = pyo.Sig(0.5)
        
        # Select between manual and auto panning
        self.pan_selector = pyo.Selector([self.pan_pos, self.pan_lfo], voice=0)
        
        # Pan control for left and right channels
        self.pan_left = pyo.SigTo(1.0, time=0.02)  # Smoothed control signal
        self.pan_right = pyo.SigTo(1.0, time=0.02)  # Smoothed control signal
        
        # Initialize pan position (center)
        # Calculate equal-power panning values for center position
        left_gain = 0.707  # sqrt(0.5)
        right_gain = 0.707
        
        # Set the pan gains directly using setValue()
        self.pan_left.setValue(left_gain)
        self.pan_right.setValue(right_gain)
        
        # Final stereo output with left and right balance
        self.l_out = self.mono_left * self.pan_left
        self.r_out = self.mono_right * self.pan_right
        
        # Width control using Interp to mix between mono and stereo
        self.mono_mix = (self.mono_left + self.mono_right) * 0.5
        self.stereo_mix = pyo.Mix([self.l_out, self.r_out], voices=2)
        self.width_processor = pyo.Interp(self.mono_mix, self.stereo_mix, interp=self.stereo_width)
        
        # Final stereo output
        self.stereo = self.width_processor
        
        # Create a dictionary to hold channel output destinations
        # Default output channels: 0=L, 1=R, 2=L Rear, 3=R Rear
        self.channel_amps = []
        self.output_channels = 4  # 4 output channels (quad)
        
        # Instead of Send objects, we'll use amplitude controllers for each channel
        for i in range(self.output_channels):
            # Create gain control for each channel (0 by default)
            channel_amp = pyo.SigTo(0, time=0.02)  # Smooth transitions for gain changes
            self.channel_amps.append(channel_amp)
            
        # Debug output - we'll have multiple backup methods for direct audio output
        if self.osc_type == "carrier":
            # For direct testing, send carrier to multiple outputs to ensure sound
            # 1. Direct stereo output
            self.direct_out = self.stereo * 0.7  # Higher volume for better audibility
            self.direct_out.out()
            
            # 2. Backup simple sine connection for most basic audio path
            self.backup_osc = pyo.Sine(freq=self.modulated_freq, mul=0.3)
            self.backup_out = self.backup_osc * self.amp_env
            self.backup_out.out()
            
            # 3. Pan object approach (works better with some audio systems)
            self.pan_backup = pyo.Pan(self.moog_filter, mul=0.4)
            self.pan_backup.out()
            
            print(f"Multiple direct outputs enabled for {self.name} - audio should definitely work")
        
        # Route destinations - each oscillator can be routed to any channel or as a mod source
        # Initialize with defaults based on oscillator type
        self.routing = {
            "destinations": [],  # List of (dest_name, amount) tuples
            "default_dest": None  # Default destination when no specific routing
        }
        
        # Set up default routing
        if self.osc_type == "carrier":
            # By default, route carriers to front L/R
            if self.name == "CAR1":
                # CAR1 to front L
                self.routing["default_dest"] = ("channel_0", 1.0)
            elif self.name == "CAR2":
                # CAR2 to front R
                self.routing["default_dest"] = ("channel_1", 1.0)
            elif self.name == "CAR3":
                # CAR3 to rear L
                self.routing["default_dest"] = ("channel_2", 1.0)
            elif self.name == "CAR4":
                # CAR4 to rear R
                self.routing["default_dest"] = ("channel_3", 1.0)
            else:
                # Default to front L/R if name doesn't match expected format
                self.routing["default_dest"] = ("channel_0", 1.0)
                
            # Apply default routing
            if self.routing["default_dest"]:
                dest, amount = self.routing["default_dest"]
                for i, amp in enumerate(self.channel_amps):
                    if f"channel_{i}" == dest:
                        amp.setValue(amount)
        
        # Output for modulation when used as an operator or a carrier
        # Both operators and carriers can be mod sources in the new routing architecture
        # Use the left delay selector which already handles filter/delay bypass
        self.mod_output = self.left_delay_selector
        
        self.initialized = True
        return True
    
    def note_on(self, note, velocity, gui):
        """Handle a MIDI note-on event with current GUI parameters"""
        if not self.initialized:
            return
            
        # Print for debugging
        print(f"Note ON - {self.name}: note={note}, velocity={velocity}")
            
        # If oscillator section is bypassed, don't trigger any sound
        if self.osc_bypass:
            print(f"{self.name} is bypassed, not triggering sound")
            return
            
        # Base frequency calculation based on mode
        if gui.freq_mode.currentText() == "Manual":
            base = gui.manual_freq.itemAt(1).widget().value()
        else:
            base = pyo.midiToHz(note)
            
        # Apply detune (both coarse and fine) only if frequency processing is not bypassed
        if not self.freq_bypass:
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

        # Apply frequency modulation if not bypassed
        if not self.freq_bypass:
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
        else:
            # If bypassed, just set a constant frequency
            self.freq_linseg.list = [(0, base)]
            self.freq_linseg.play()
            self.freq_adsr.mul = 0  # Disable frequency envelope

        # Apply amplitude envelope if not bypassed
        if not self.amp_bypass:
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
        else:
            # If bypassed, use constant amplitude
            self.amp_ramp.list = [(0, 1.0)]
            self.amp_ramp.play()

        # Apply filter if not bypassed
        if not self.filter_bypass:
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
            
            # Ensure filter is in the signal chain
            self.filter_selector.voice = 1
        else:
            # When bypassed, use voice 0 which bypasses the filter
            self.filter_selector.voice = 0

        # Feedback routing
        source = gui.feedback_source.currentText()
        depth = gui.feedback_depth.itemAt(1).widget().value()

        if source == "Pre-Delay" and not self.filter_bypass:
            feedback_signal = self.moog_filter  # Use the filter output
        elif source == "Post-Delay" and not self.delay_bypass:
            feedback_signal = pyo.Mix(self.stereo, voices=1)
        else:
            feedback_signal = pyo.Sig(0)

        self.modulated_freq = self.final_freq + (feedback_signal * depth)
        self.osc.freq = self.modulated_freq

        # Amplitude envelope if not bypassed
        if not self.amp_bypass:
            # Get envelope parameters from GUI
            attack = gui.amp_attack.itemAt(1).widget().value()
            decay = gui.amp_decay.itemAt(1).widget().value()
            sustain = gui.amp_sustain.itemAt(1).widget().value()
            release = gui.amp_release.itemAt(1).widget().value()
            
            # Set envelope parameters with default fallbacks
            self.amp_env.setAttack(attack if attack > 0 else 0.01)
            self.amp_env.setDecay(decay if decay > 0 else 0.1)
            self.amp_env.setSustain(sustain)
            self.amp_env.setRelease(release if release > 0 else 0.1)
            
            # Use higher volume for better audibility
            self.amp_env.mul = 1.0  # Full amplitude for direct output
            
            # Play the envelope and log settings
            self.amp_env.play()
            print(f"{self.name}: Playing with envelope A={self.amp_env.attack}, D={self.amp_env.decay}, " + 
                  f"S={self.amp_env.sustain}, R={self.amp_env.release}")
        else:
            # Constant amplitude when bypassed - use immediate attack/release
            self.amp_env.setAttack(0.01)
            self.amp_env.setDecay(0.01)
            self.amp_env.setSustain(1.0)
            self.amp_env.setRelease(0.01)
            
            # Use full amplitude for better audibility
            self.amp_env.mul = 1.0
            
            # Play the envelope and log settings
            self.amp_env.play()
            print(f"{self.name}: Playing with constant amplitude (bypass mode)")

        # Delay update if not bypassed
        if not self.delay_bypass:
            self.left_delay.delay = self._get_delays(gui.left_delays)
            self.right_delay.delay = self._get_delays(gui.right_delays)
            self.left_delay.feedback = gui.left_feedback.itemAt(1).widget().value()
            self.right_delay.feedback = gui.right_feedback.itemAt(1).widget().value()
            
            # Ensure delays are in the signal chain
            self.left_delay_selector.voice = 1
            self.right_delay_selector.voice = 1
        else:
            # When bypassed, use voice 0 which bypasses the delays
            self.left_delay_selector.voice = 0
            self.right_delay_selector.voice = 0

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
        """Get the modulation output signal (for operators or carriers)"""
        if self.initialized:
            return self.mod_output
        return None
            
    def set_routing(self, destinations, clear_existing=True):
        """Set the routing for this oscillator
        
        Args:
            destinations: List of (destination, amount) tuples, where destination is
                         either "channel_N" or an oscillator instance
            clear_existing: Whether to clear existing routing before applying new routing
        """
        if not self.initialized:
            return
            
        # Clear existing routing if requested
        if clear_existing:
            # Clear all amplitudes
            for amp in self.channel_amps:
                amp.setValue(0)
                
            # Clear destinations list
            self.routing["destinations"] = []
        
        # Add new destinations
        for dest, amount in destinations:
            self.routing["destinations"].append((dest, amount))
            
            # Check if the destination is a channel number
            if isinstance(dest, str) and dest.startswith("channel_"):
                try:
                    channel = int(dest.split("_")[1])
                    if 0 <= channel < len(self.channel_amps):
                        # Set the amount for this channel
                        self.channel_amps[channel].setValue(amount)
                except (ValueError, IndexError):
                    print(f"Invalid channel: {dest}")
                    
    def add_routing(self, destination, amount=1.0):
        """Add a routing destination without clearing existing routing
        
        Args:
            destination: Either "channel_N" or an oscillator instance
            amount: The amount to send to the destination
        """
        self.set_routing([(destination, amount)], clear_existing=False)
            
    def clear_routing(self):
        """Clear all routing for this oscillator"""
        self.set_routing([], clear_existing=True)
        
    def set_bypass(self, section, state):
        """Set bypass state for a specific section
        
        Args:
            section (str): The section to bypass ('osc', 'freq', 'amp', 'filter', 'delay')
            state (bool): True to bypass, False to enable
        """
        if not self.initialized:
            return
            
        if section == 'filter' and self.filter_bypass != state:
            self.filter_bypass = state
            # Voice 0 bypasses the filter, voice 1 uses it
            self.filter_selector.voice = 0 if state else 1
            
        elif section == 'delay' and self.delay_bypass != state:
            self.delay_bypass = state
            # Voice 0 bypasses the delay, voice 1 uses it
            self.left_delay_selector.voice = 0 if state else 1
            self.right_delay_selector.voice = 0 if state else 1
            
        elif section == 'osc':
            self.osc_bypass = state
            # Oscillator bypass is handled differently - we just mute it
            if state:
                self.osc.mul = 0  # Mute oscillator
            # We don't unmute here as that's controlled by amp envelope
            
        elif section == 'freq':
            self.freq_bypass = state
            # When bypassing frequency processing, we hold at the base frequency
            # Implementation will depend on what gui is active - handled in note_on
            
        elif section == 'amp':
            self.amp_bypass = state
            # When bypassing amplitude envelope, we use a constant gain of 1
            if state:
                self.amp_env.mul = 1
                self.amp_ramp.mul = 1
            # We don't reset here as that's handled in note_on
            
    def get_bypass_state(self, section):
        """Get the bypass state for a specific section
        
        Args:
            section (str): The section to check ('osc', 'freq', 'amp', 'filter', 'delay')
            
        Returns:
            bool: True if bypassed, False if enabled
        """
        if section == 'osc':
            return self.osc_bypass
        elif section == 'freq':
            return self.freq_bypass
        elif section == 'amp':
            return self.amp_bypass
        elif section == 'filter':
            return self.filter_bypass
        elif section == 'delay':
            return self.delay_bypass
        return False
        
    def set_pan_position(self, position):
        """Set the manual pan position
        
        Args:
            position (float): Pan position from 0.0 (left) to 1.0 (right)
        """
        if not self.initialized:
            return
            
        # Clamp to valid range
        position = max(0.0, min(1.0, position))
        
        # Update the position signal
        try:
            self.pan_pos.setValue(position)
        except AttributeError:
            # Fallback to direct assignment
            self.pan_pos.value = position
        
        # Ensure we're using manual panning
        if self.use_autopan:
            self.use_autopan = False
            self.pan_selector.voice = 0
            
        # Calculate equal-power panning values
        # This gives better volume balance across the stereo field
        left_gain = (1.0 - position) ** 0.5
        right_gain = position ** 0.5
        
        # Set the pan gains with smooth transitions
        self.pan_left.setValue(left_gain)
        self.pan_right.setValue(right_gain)
            
    def set_stereo_width(self, width):
        """Set the stereo width
        
        Args:
            width (float): Width from 0.0 (mono) to 1.0 (full stereo)
        """
        if not self.initialized:
            return
            
        # Clamp to valid range
        width = max(0.0, min(1.0, width))
        self.stereo_width = width
        self.width_processor.interp = width
        
    def set_autopan(self, enabled, rate=None):
        """Enable or disable autopanning
        
        Args:
            enabled (bool): True to enable autopanning, False to use manual pan
            rate (float, optional): LFO frequency in Hz (if None, keep current)
        """
        if not self.initialized:
            return
            
        # Set autopan state
        self.use_autopan = enabled
        self.pan_selector.voice = 1 if enabled else 0
        
        # Update LFO rate if provided
        if rate is not None:
            self.pan_lfo.freq = rate
    
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
        
        # Clear panner components
        self.width_processor = None
        self.mono_mix = None
        self.stereo_mix = None
        self.l_out = None
        self.r_out = None
        self.pan_left = None
        self.pan_right = None
        self.mono_left = None
        self.mono_right = None
        self.pan_pos = None
        self.pan_lfo = None
        self.pan_selector = None
        
        # Clear selector components
        self.left_delay_selector = None
        self.right_delay_selector = None
        self.filter_selector = None
        
        # Clear original components
        self.left_delay = None
        self.right_delay = None
        self.moog_filter = None
        self.osc = None
        self.amp_env = None
        self.freq_adsr = None
        self.freq_linseg = None
        self.amp_ramp = None
        
        self.initialized = False
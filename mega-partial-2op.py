import yaml
import os
from pyo import *
import mido
from threading import Thread

class Oscillator:
    def __init__(self, name, role="operator", ratio=1.0, index=1.0, freq_offset=0.0):
        # Basic parameters
        self.name = name
        self.role = role
        self.ratio = Sig(ratio)
        self.index = Sig(index)
        self.freq_offset = Sig(freq_offset)
        
        # Waveform
        self.table = HarmTable([1])  # Default to sine wave
        
        # ADSR envelopes
        self.freq_env = Adsr(attack=0.01, decay=0.1, sustain=0.5, release=0.3, dur=1, mul=50)
        self.amp_env = Adsr(attack=0.01, decay=0.1, sustain=0.5, release=0.3, dur=1, mul=0.5)
        
        # Envelope delays
        self.freq_delay = Sig(0.0)
        self.depth_delay = Sig(0.0)
        
        # Frequency ramp parameters
        self.freq_ramp_start = Sig(0.0)
        self.freq_ramp_end = Sig(0.0)
        self.freq_ramp_time = Sig(1.0)
        self.freq_ramp = Linseg([(0, self.freq_ramp_start.value), 
                                (self.freq_ramp_time.value, self.freq_ramp_end.value)])
        
        # Amplitude ramp parameters
        self.amp_ramp_start = Sig(1.0)
        self.amp_ramp_end = Sig(1.0)
        self.amp_ramp_time = Sig(1.0)
        self.amp_ramp = Linseg([(0, self.amp_ramp_start.value), 
                               (self.amp_ramp_time.value, self.amp_ramp_end.value)])
        
        # Phase control
        self.phase = Sig(0.0)
        
        # The oscillator itself - will be properly connected in the synth class
        self.osc = None
        self.freq = None
        self.amp = None
        
    def update_ramps(self):
        """Update ramp segments based on current parameter values"""
        # Update frequency ramp
        freq_time = max(0.01, self.freq_ramp_time.get())
        self.freq_ramp.setList([
            (0, self.freq_ramp_start.get()),
            (freq_time, self.freq_ramp_end.get())
        ])
        
        # Update amplitude ramp
        amp_time = max(0.01, self.amp_ramp_time.get())
        self.amp_ramp.setList([
            (0, self.amp_ramp_start.get()),
            (amp_time, self.amp_ramp_end.get())
        ])
    
    def play(self):
        """Trigger the oscillator"""
        # Play envelopes with delays
        CallAfter(self.freq_env.play, self.freq_delay.value)
        CallAfter(self.amp_env.play, self.depth_delay.value)
        
        # Reset and play ramps
        self.freq_ramp.play()
        self.amp_ramp.play()
    
    def stop(self):
        """Release the oscillator"""
        CallAfter(self.freq_env.stop, self.freq_delay.value)
        CallAfter(self.amp_env.stop, self.depth_delay.value)
        # Ramps complete on their own
    
    def setup_gui(self):
        """Create GUI controls for this oscillator"""
        self.ratio.ctrl(title=f"{self.name} Ratio")
        self.index.ctrl(title=f"{self.name} Index")
        self.freq_offset.ctrl(title=f"{self.name} Freq Offset")
        
        self.freq_env.ctrl(title=f"{self.name} Freq Env")
        self.amp_env.ctrl(title=f"{self.name} Amp Env")
        
        self.freq_delay.ctrl(title=f"{self.name} Freq Delay (sec)")
        self.depth_delay.ctrl(title=f"{self.name} Depth Delay (sec)")
        
        self.freq_ramp_start.ctrl(title=f"{self.name} Freq Ramp Start")
        self.freq_ramp_end.ctrl(title=f"{self.name} Freq Ramp End")
        self.freq_ramp_time.ctrl(title=f"{self.name} Freq Ramp Time (sec)")
        
        self.amp_ramp_start.ctrl(title=f"{self.name} Amp Ramp Start")
        self.amp_ramp_end.ctrl(title=f"{self.name} Amp Ramp End")
        self.amp_ramp_time.ctrl(title=f"{self.name} Amp Ramp Time (sec)")
        
        self.phase.ctrl(title=f"{self.name} Phase")
        
    def get_parameters(self):
        """Return a dictionary with all parameters for saving"""
        params = {
            "ratio": self.ratio.get(),
            "index": self.index.get(),
            "freq_offset": self.freq_offset.get(),
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
                "time": self.freq_ramp_time.get()
            },
            "amp_ramp": {
                "start": self.amp_ramp_start.get(),
                "end": self.amp_ramp_end.get(),
                "time": self.amp_ramp_time.get()
            }
        }
        return params
    
    def load_parameters(self, params):
        """Load parameters from a dictionary"""
        # Basic parameters
        self.ratio.value = params.get("ratio", 1.0)
        self.index.value = params.get("index", 1.0)
        self.freq_offset.value = params.get("freq_offset", 0.0)
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
        self.amp_env.mul = amp_env_params.get("mul", 0.5)
        
        # Delay parameters
        self.freq_delay.value = params.get("freq_delay", 0.0)
        self.depth_delay.value = params.get("depth_delay", 0.0)
        
        # Ramp parameters
        freq_ramp_params = params.get("freq_ramp", {})
        self.freq_ramp_start.value = freq_ramp_params.get("start", 0.0)
        self.freq_ramp_end.value = freq_ramp_params.get("end", 0.0)
        self.freq_ramp_time.value = freq_ramp_params.get("time", 1.0)
        
        amp_ramp_params = params.get("amp_ramp", {})
        self.amp_ramp_start.value = amp_ramp_params.get("start", 1.0)
        self.amp_ramp_end.value = amp_ramp_params.get("end", 1.0)
        self.amp_ramp_time.value = amp_ramp_params.get("time", 1.0)
        
        # Update ramps with the new parameters
        self.update_ramps()


class MegaPartial2Op:
    def __init__(self, preset_file="caelus_preset.yaml"):
        # Store preset file path
        self.preset_file = preset_file
        
        # Boot the audio server with stereo output
        self.s = Server(nchnls=2).boot()
        
        # === Control signals ===
        self.pitch = Sig(440.0)
        self.velocity = Sig(0.0)
        self.aftertouch = Sig(0.0)
        
        # Create operators with the unified Oscillator class
        self.op1 = Oscillator("Op1", role="modulator", ratio=3.0, index=1.0)
        self.op2 = Oscillator("Op2", role="modulator", ratio=1.0, index=0.8)
        self.carrier = Oscillator("Carrier", role="carrier", ratio=1.0, index=0.0)
        
        # Configure specific parameters to match original presets
        # Operator 1
        self.op1.freq_env = Adsr(attack=0.005, decay=1.5, sustain=0.1, release=0.8, dur=1, mul=1.0)
        self.op1.amp_ramp_end.value = 0.5
        self.op1.amp_ramp_time.value = 1.2
        
        # Operator 2
        self.op2.freq_env = Adsr(attack=0.01, decay=0.8, sustain=0.4, release=0.6, dur=1, mul=1.0) 
        self.op2.amp_ramp_end.value = 0.7
        self.op2.amp_ramp_time.value = 0.9
        
        # Carrier
        self.carrier.amp_env = Adsr(attack=0.01, decay=0.1, sustain=0.8, release=0.5, dur=1, mul=0.15)
        self.carrier.amp_ramp_end.value = 0.8
        self.carrier.amp_ramp_time.value = 1.5
        
        # Try to load preset parameters if file exists
        self.load_preset()
        
        # Set up triggers to update ramps when parameters change
        param_trigger = Change(
            self.op1.freq_ramp_start + self.op1.freq_ramp_end + self.op1.freq_ramp_time + 
            self.op1.amp_ramp_start + self.op1.amp_ramp_end + self.op1.amp_ramp_time +
            self.op2.freq_ramp_start + self.op2.freq_ramp_end + self.op2.freq_ramp_time + 
            self.op2.amp_ramp_start + self.op2.amp_ramp_end + self.op2.amp_ramp_time +
            self.carrier.freq_ramp_start + self.carrier.freq_ramp_end + self.carrier.freq_ramp_time + 
            self.carrier.amp_ramp_start + self.carrier.amp_ramp_end + self.carrier.amp_ramp_time
        ).play()
        
        self.param_updater = TrigFunc(param_trigger, self.update_all_ramps)
        
        # Set up the FM chain and output
        self.setup_chain()
        
        # Set up GUI
        self.setup_gui()
        
        # Initialize active notes list for MIDI
        self.active_notes = []
        
        # Update ramps once to initialize
        self.update_all_ramps()
        
        # Launch MIDI handler
        Thread(target=self.midi_loop, daemon=True).start()
        
        # Use atexit to register the save function
        import atexit
        atexit.register(self.save_preset)
        
        # Start the server last
        self.s.start()
    
    def on_server_close(self):
        """Save the preset when the server is closed"""
        # Use a flag to prevent multiple calls
        if not hasattr(self, '_closing'):
            self._closing = True
            print("Saving preset...")
            self.save_preset()
        
    def save_preset(self):
        """Save all parameters to a preset file"""
        preset_data = {
            "particle1": {
                "op1": self.op1.get_parameters(),
                "op2": self.op2.get_parameters(),
                "carrier": self.carrier.get_parameters()
            }
        }
        
        try:
            with open(self.preset_file, 'w') as f:
                yaml.dump(preset_data, f, default_flow_style=False, sort_keys=False)
            print(f"Preset saved to {self.preset_file}")
        except Exception as e:
            print(f"Error saving preset: {e}")
    
    def load_preset(self):
        """Load parameters from a preset file if it exists"""
        if not os.path.exists(self.preset_file):
            print(f"No preset file found at {self.preset_file}, using defaults")
            return
        
        try:
            with open(self.preset_file, 'r') as f:
                preset_data = yaml.safe_load(f)
            
            # Try to load from the new structure
            if "particle1" in preset_data:
                particle_data = preset_data["particle1"]
                
                if "op1" in particle_data:
                    self.op1.load_parameters(particle_data["op1"])
                
                if "op2" in particle_data:
                    self.op2.load_parameters(particle_data["op2"])
                
                if "carrier" in particle_data:
                    self.carrier.load_parameters(particle_data["carrier"])
            
            # Fallback to old structure if needed
            elif "op1" in preset_data:
                print("Loading from legacy preset format")
                self.op1.load_parameters(preset_data["op1"])
                
                if "op2" in preset_data:
                    self.op2.load_parameters(preset_data["op2"])
                
                if "carrier" in preset_data:
                    self.carrier.load_parameters(preset_data["carrier"])
            
            print(f"Preset loaded from {self.preset_file}")
        except Exception as e:
            print(f"Error loading preset: {e}")
    
    def update_all_ramps(self):
        """Update all operator ramps"""
        self.op1.update_ramps()
        self.op2.update_ramps()
        self.carrier.update_ramps()
    
    def setup_chain(self):
        """Connect the operators in the FM chain"""
        # Operator 1 calculations
        self.op1.base_freq = self.pitch * self.op1.ratio + self.op1.freq_offset
        self.op1.freq = self.op1.base_freq + (self.op1.freq_ramp * self.pitch)
        self.op1.amp = self.pitch * self.op1.index * self.op1.amp_env * self.op1.amp_ramp
        self.op1.osc = Sine(freq=self.op1.freq, mul=self.op1.amp)
        
        # Operator 2 calculations
        self.op2.base_freq = self.pitch * self.op2.ratio + self.op2.freq_offset
        self.op2.freq = self.op2.base_freq + (self.op2.freq_ramp * self.pitch) + self.op1.osc
        self.op2.amp = self.pitch * self.op2.index * self.op2.amp_env * self.op2.amp_ramp
        self.op2.osc = Sine(freq=self.op2.freq, mul=self.op2.amp)
        
        # Carrier calculations
        self.carrier.base_freq = self.pitch
        self.carrier.freq = self.carrier.base_freq + (self.carrier.freq_ramp * self.pitch) + self.op2.osc
        self.carrier.osc = Sine(
            freq=self.carrier.freq,
            mul=self.carrier.amp_env * self.velocity * (0.5 + self.aftertouch**2 * 2) * self.carrier.amp_ramp
        )
        
        # === STEREO OUTPUT WITH CENTER PANNING ===
        self.panner = Pan(self.carrier.osc, outs=2, pan=0.5)
        
        # === AUDIO OUTPUT WITH LIMITER ===
        self.limiter = Compress(
            input=self.panner,
            thresh=-12,
            ratio=20,
            risetime=0.001,
            falltime=0.1,
            lookahead=5,
            knee=0.5,
            outputAmp=False
        )
        
        self.final = self.limiter * 0.7
        self.final.out()
    
    def play_note(self, note, velocity_val):
        """Play a note with the given velocity"""
        freq_val = 440.0 * (2 ** ((note - 69) / 12))
        self.pitch.value = freq_val
        self.velocity.value = velocity_val / 127
        
        # Play operator envelopes
        self.carrier.amp_env.play()
        self.op1.freq_env.play()
        self.op1.amp_env.play()
        self.op2.freq_env.play()
        self.op2.amp_env.play()
        
        # Force an update of the ramps
        self.update_all_ramps()
        
        # Play operator ramps
        self.op1.freq_ramp.play()
        self.op1.amp_ramp.play()
        self.op2.freq_ramp.play()
        self.op2.amp_ramp.play()
        self.carrier.freq_ramp.play()
        self.carrier.amp_ramp.play()
    
    def stop_note(self):
        """Stop the current note"""
        # Stop all envelopes
        self.carrier.amp_env.stop()
        self.op1.freq_env.stop()
        self.op1.amp_env.stop()
        self.op2.freq_env.stop()
        self.op2.amp_env.stop()
    
    def midi_loop(self):
        """Handle MIDI input"""
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
        """Set up the GUI controls"""
        # Operator 1 GUI
        self.op1.setup_gui()
        
        # Operator 2 GUI
        self.op2.setup_gui()
        
        # Carrier GUI
        self.carrier.setup_gui()
        self.carrier.amp_env.ctrl(title="Carrier Amplitude Envelope")

# Run the synthesizer
if __name__ == "__main__":
    synth = MegaPartial2Op()
    synth.s.gui(locals())
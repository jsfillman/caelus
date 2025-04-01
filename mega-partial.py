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

class MegaPartial2Op:
    def __init__(self):
        # Boot the audio server with stereo output
        self.s = Server(nchnls=2).boot()
        self.s.start()
        
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
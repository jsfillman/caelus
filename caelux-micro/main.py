import pyo
import mido
import random
import atexit

from PyQt5.QtWidgets import QApplication
from synth_ui import SynthUI
from wavetables import WaveformBank
from settings import load_patch, save_patch

# Default patch file
PATCH_FILE = "last_patch.yaml"

# --------- Qt App Setup First ---------
app = QApplication([])

# --------- AUDIO SETUP Second ---------
s = pyo.Server().boot()
s.start()

# --------- WAVEFORM TABLES Setup ---------
wave_bank = WaveformBank()
wave_bank.create_standard_tables()  # Create tables now that server is running

# --------- GUI Setup ---------
gui = SynthUI(s)  # Pass the server to SynthUI
gui.show()

# Load the last patch if available
load_patch(PATCH_FILE, gui)

# Register function to save patch on exit
def save_on_exit():
    save_patch(PATCH_FILE, gui)

atexit.register(save_on_exit)

# --------- MIDI SETUP ---------
print("Available MIDI input ports:")
midi_inputs = mido.get_input_names()
for i, name in enumerate(midi_inputs):
    print(f"[{i}] {name}")

# Try to select a default MIDI device if one exists
if midi_inputs:
    try:
        index = int(input("Select MIDI input device by number: "))
        midi_port = mido.open_input(midi_inputs[index])
        print(f"Using MIDI input: {midi_inputs[index]}")
    except (ValueError, IndexError):
        print("Invalid selection, using first available MIDI port")
        midi_port = mido.open_input(midi_inputs[0])
        print(f"Using MIDI input: {midi_inputs[0]}")
else:
    print("No MIDI devices found!")
    # Create a dummy MIDI port for testing
    midi_port = None

# State
pitch_bend_range = 2  # semitones
current_pitch_bend = 0.0
sustain_on = False
note_is_held = False

# Amp control: ramp → ADSR
amp_ramp = pyo.Linseg([(0, 0), (1, 1)], loop=False)
amp_env = pyo.Adsr(attack=0.01, decay=0.1, sustain=0.7, release=0.5, dur=0, mul=amp_ramp)

# Freq control: ADSR (in Hz) + Linseg glide
freq_adsr = pyo.Adsr(attack=0.01, decay=0.1, sustain=1.0, release=0.5, dur=0, mul=0)
freq_linseg = pyo.Linseg([(0, 440), (1, 440)], loop=False)
final_freq = freq_linseg + freq_adsr

# Placeholder for modulated frequency and osc
modulated_freq = final_freq
num_oscillators = 8  # This will come from the GUI later
detune = 0.001       # Will come from GUI
table_name = "sine"  # Will come from GUI dropdown

base_freqs = []
for i in range(num_oscillators):
    detune_factor = 1.0 + (detune * (i - (num_oscillators//2)))
    base_freqs.append(modulated_freq * detune_factor)

osc = pyo.OscBank(
    table=wave_bank.get_table(table_name),
    freq=base_freqs,
    spread=0.1,      # Will be controlled by GUI
    num=num_oscillators,
    mul=amp_env
)

# --------- LPF Filter Controls ---------
filter_ramp = pyo.Linseg([(0, 100), (1, 5000)], loop=False)
moog_filter = pyo.MoogLP(osc, freq=filter_ramp, res=0.3)

# --------- Stereo Multitap Delay ---------
def get_delays(slider_list):
    return [slider.itemAt(1).widget().value() for slider in slider_list]

left_delay = pyo.Delay(moog_filter, delay=[0.15, 0.35, 0.55], feedback=0.3, mul=0.3)
right_delay = pyo.Delay(moog_filter, delay=[0.2, 0.4, 0.6], feedback=0.3, mul=0.3)
l_pan = pyo.Pan(left_delay, outs=2, pan=0.0)
r_pan = pyo.Pan(right_delay, outs=2, pan=1.0)
stereo = l_pan + r_pan
stereo.out()

current_note = {'note': None}

# --------- MIDI HANDLER ---------
def midi_loop():
    global current_pitch_bend, sustain_on, note_is_held, osc

    for msg in midi_port.iter_pending():
        if msg.type == 'note_on' and msg.velocity > 0:
            # Base frequency calculation based on mode
            if gui.freq_mode.currentText() == "Manual":
                base = gui.manual_freq.itemAt(1).widget().value()
            else:
                base = pyo.midiToHz(msg.note)
                
            # Apply detune (both coarse and fine)
            coarse_detune = gui.coarse_detune.itemAt(1).widget().value()
            fine_detune = gui.fine_detune.itemAt(1).widget().value() / 100.0  # Convert cents to semitones
            detune_factor = 2 ** ((coarse_detune + fine_detune) / 12.0)
            base *= detune_factor

            # Apply pitch bend
            bend_ratio = 2 ** (current_pitch_bend / 12.0)
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
            current_table = wave_bank.get_table(wave_type)
            
            # Create a list of phase offsets based on the phase spread
            phases = []
            for i in range(num_oscs):
                if phase_spread > 0:
                    phases.append((i / num_oscs) * phase_spread)
                else:
                    phases.append(0)
            
            # Now rebuild the oscillator
            osc.table = current_table
            osc.freq = base_freqs
            osc.spread = spread_val
            osc.mul = [amp_env * amp for amp in base_amps]
            osc.phase = phases


            # Get parameters from GUI for frequency
            start_rand = gui.start_rand.itemAt(1).widget().value()
            start_slew = gui.start_slew.itemAt(1).widget().value()
            end_slew = gui.end_slew.itemAt(1).widget().value()
            slew_time = gui.slew_time.itemAt(1).widget().value()
            slew_delay = gui.slew_delay.itemAt(1).widget().value()

            # Configure frequency ADSR
            freq_adsr.setAttack(gui.freq_attack.itemAt(1).widget().value())
            freq_adsr.setDecay(gui.freq_decay.itemAt(1).widget().value())
            freq_adsr.setSustain(gui.freq_sustain.itemAt(1).widget().value())
            freq_adsr.setRelease(gui.freq_release.itemAt(1).widget().value())
            
            # Set frequency envelope depth/intensity
            freq_env_depth = gui.freq_env_depth.itemAt(1).widget().value()
            freq_adsr.mul = freq_env_depth
            
            # Calculate frequencies with randomization
            freq_start = base + start_slew + random.uniform(-start_rand, start_rand)
            freq_end = base + end_slew
            
            # Set up the Linseg with delay before ramping
            if slew_delay > 0:
                freq_linseg.list = [(0, freq_start), (slew_delay, freq_start), (slew_delay + slew_time, freq_end)]
            else:
                freq_linseg.list = [(0, freq_start), (slew_time, freq_end)]
                
            freq_linseg.play()
            freq_adsr.play()

            # Get amplitude ramp parameters including the new delay
            amp_start = gui.amp_ramp_start.itemAt(1).widget().value()
            amp_end = gui.amp_ramp_end.itemAt(1).widget().value()
            amp_time = gui.amp_ramp_time.itemAt(1).widget().value()
            amp_delay = gui.amp_ramp_delay.itemAt(1).widget().value()
            
            # Set up amplitude ramp with delay
            if amp_delay > 0:
                amp_ramp.list = [(0, amp_start), (amp_delay, amp_start), (amp_delay + amp_time, amp_end)]
            else:
                amp_ramp.list = [(0, amp_start), (amp_time, amp_end)]
                
            amp_ramp.play()

            # Configure filter parameters
            filter_res = gui.filter_res.itemAt(1).widget().value()
            
            # Get filter ramp parameters
            filter_start = gui.filter_ramp_start.itemAt(1).widget().value()
            filter_end = gui.filter_ramp_end.itemAt(1).widget().value()
            filter_time = gui.filter_ramp_time.itemAt(1).widget().value()
            filter_delay = gui.filter_ramp_delay.itemAt(1).widget().value()
            
            # Set up filter ramp with delay
            if filter_delay > 0:
                filter_ramp.list = [(0, filter_start), (filter_delay, filter_start), (filter_delay + filter_time, filter_end)]
            else:
                filter_ramp.list = [(0, filter_start), (filter_time, filter_end)]
                
            filter_ramp.play()
            
            # Update the filter resonance
            moog_filter.res = filter_res

            # Feedback routing
            source = gui.feedback_source.currentText()
            depth = gui.feedback_depth.itemAt(1).widget().value()

            if source == "Pre-Delay":
                feedback_signal = moog_filter  # Now use the filter output
            elif source == "Post-Delay":
                feedback_signal = pyo.Mix(stereo, voices=1)
            else:
                feedback_signal = pyo.Sig(0)

            modulated_freq = final_freq + (feedback_signal * depth)
            osc.freq = modulated_freq

            # Amplitude envelope
            amp_env.setAttack(gui.amp_attack.itemAt(1).widget().value())
            amp_env.setDecay(gui.amp_decay.itemAt(1).widget().value())
            amp_env.setSustain(gui.amp_sustain.itemAt(1).widget().value())
            amp_env.setRelease(gui.amp_release.itemAt(1).widget().value())
            amp_env.play()

            # Delay update
            left_delay.delay = get_delays(gui.left_delays)
            right_delay.delay = get_delays(gui.right_delays)
            left_delay.feedback = gui.left_feedback.itemAt(1).widget().value()
            right_delay.feedback = gui.right_feedback.itemAt(1).widget().value()

            current_note['note'] = msg.note
            note_is_held = True

        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            if msg.note == current_note['note']:
                note_is_held = False
                if not sustain_on:
                    amp_env.stop()
                    freq_adsr.stop()
                    current_note['note'] = None

        elif msg.type == 'polytouch':
            if msg.note == current_note['note']:
                amp_env.setSustain(msg.value / 127.0)

        elif msg.type == 'aftertouch':
            if current_note['note'] is not None:
                amp_env.setSustain(msg.value / 127.0)

        elif msg.type == 'pitchwheel':
            normalized = msg.pitch / 8192.0
            current_pitch_bend = normalized * pitch_bend_range

        elif msg.type == 'control_change' and msg.control == 64:
            if msg.value >= 64:
                sustain_on = True
            else:
                sustain_on = False
                if not note_is_held and current_note['note'] is not None:
                    amp_env.stop()
                    freq_adsr.stop()
                    current_note['note'] = None

# Poll MIDI
if midi_port:
    pat = pyo.Pattern(midi_loop, time=0.01).play()

# Start the app
app.exec_()

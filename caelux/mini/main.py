import pyo
import mido
import random

from PyQt5.QtWidgets import QApplication
from synth_ui import SynthUI

# --------- Qt App & GUI Setup ---------
app = QApplication([])
gui = SynthUI()
gui.show()

# --------- MIDI SETUP ---------
print("Available MIDI input ports:")
midi_inputs = mido.get_input_names()
for i, name in enumerate(midi_inputs):
    print(f"[{i}] {name}")

index = int(input("Select MIDI input device by number: "))
midi_port = mido.open_input(midi_inputs[index])
print(f"Using MIDI input: {midi_inputs[index]}")

# --------- AUDIO SETUP ---------
s = pyo.Server().boot()
s.start()

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
osc = pyo.Sine(freq=modulated_freq, mul=amp_env)

# --------- Stereo Multitap Delay ---------
def get_delays(slider_list):
    return [slider.itemAt(1).widget().value() for slider in slider_list]

left_delay = pyo.Delay(osc, delay=[0.15, 0.35, 0.55], feedback=0.3, mul=0.3)
right_delay = pyo.Delay(osc, delay=[0.2, 0.4, 0.6], feedback=0.3, mul=0.3)
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

            # GUI params
            start_rand = gui.start_rand.itemAt(1).widget().value()
            start_slew = gui.start_slew.itemAt(1).widget().value()
            end_slew = gui.end_slew.itemAt(1).widget().value()
            slew_time = gui.slew_time.itemAt(1).widget().value()

            freq_adsr.setAttack(gui.freq_attack.itemAt(1).widget().value())
            freq_adsr.setDecay(gui.freq_decay.itemAt(1).widget().value())
            freq_adsr.setSustain(gui.freq_sustain.itemAt(1).widget().value())
            freq_adsr.setRelease(gui.freq_release.itemAt(1).widget().value())
            freq_adsr.mul = gui.freq_env_depth.itemAt(1).widget().value()

            freq_start = base + start_slew + random.uniform(-start_rand, start_rand)
            freq_end = base + end_slew
            freq_linseg.list = [(0, freq_start), (slew_time, freq_end)]
            freq_linseg.play()
            freq_adsr.play()

            final_freq = freq_linseg + freq_adsr

            # Feedback routing
            source = gui.feedback_source.currentText()
            depth = gui.feedback_depth.itemAt(1).widget().value()

            if source == "Pre-Delay":
                feedback_signal = osc
            elif source == "Post-Delay":
                feedback_signal = pyo.Mix(stereo, voices=1)
            else:
                feedback_signal = pyo.Sig(0)

            modulated_freq = final_freq + (feedback_signal * depth)
            osc.freq = modulated_freq

            # Amplitude envelope
            amp_start = gui.amp_ramp_start.itemAt(1).widget().value()
            amp_end = gui.amp_ramp_end.itemAt(1).widget().value()
            amp_time = gui.amp_ramp_time.itemAt(1).widget().value()
            amp_ramp.list = [(0, amp_start), (amp_time, amp_end)]
            amp_ramp.play()

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
pat = pyo.Pattern(midi_loop, time=0.01).play()
app.exec_()
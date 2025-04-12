# main.py
import pyo
from ui import run_ui
from setup import select_audio_device, select_midi_device, select_num_channels, start_server
from midi_handler import start_midi_listener
from oscillator import Oscillator
from wavetables import WaveformBank


# === SETUP ===
audio_index = select_audio_device()
nchnls = select_num_channels()  
midi_port = select_midi_device()
s = start_server(audio_index, nchnls)  

# Set up waveform bank
waveform_bank = WaveformBank().create_standard_tables()


freq = pyo.Sig(0)
amp = pyo.Sig(0)
vol_control = pyo.Sig(11)
vol = vol_control * (0.8 / 11)

oscillators = []
for i in range(8):
    osc = Oscillator(freq, amp, vol, out_chnl=i,  waveform_bank=waveform_bank, table_name="triangle")
    oscillators.append(osc)

def trigger_note(event_type, note, value):
    if event_type == "note_on":
        print(f"Note ON: {note}, velocity: {value}")
        freq.value = pyo.midiToHz(note)
        amp.value = value / 127.0 * 0.2
        for osc in oscillators:
            osc.env.play()
    elif event_type == "note_off":
        print(f"Note OFF: {note}")
        amp.value = 0
        for osc in oscillators:
            osc.env.play()
    elif event_type == "polytouch":
        print(f"Poly AT: note {note}, value {value}")
        amp.value = value / 127.0 * 0.3
    elif event_type == "aftertouch":
        print(f"Channel AT: value {value}")
        amp.value = value / 127.0 * 0.3

# === CALLBACK ===

## Alt version
# MIDI_HANDLERS = [trigger_note, set_wave, set_osc_num]

# def on_midi(event_type, note, value):
#     for handler in MIDI_HANDLERS:
#         handler(event_type, note, value)

def on_midi(event_type, note, value):
    trigger_note(event_type, note, value)
    # set_wave(event_type, note, value)
    # set_osc_num(event_type, note, value)


# === MIDI LISTENER ===
start_midi_listener(midi_port, on_midi)



def get_ui_controls(self):
    return self.semi, self.cents, self


def set_attack(self, val): self.attack_val = val; self.env.setAttack(val)
def set_decay(self, val): self.decay_val = val; self.env.setDecay(val)
def set_sustain(self, val): self.sustain_val = val; self.env.setSustain(val)
def set_release(self, val): self.release_val = val; self.env.setRelease(val)

run_ui(vol_control, oscillators, waveform_bank)


# === RUN ===
input("\nPress Enter to quit...\n")
s.stop()




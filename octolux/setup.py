# setup.py
import pyo
import mido

def select_audio_device():
    print("=== AUDIO DEVICES ===")
    pyo.pa_list_devices()
    return int(input("Select audio output device index: "))

def select_num_channels():
    return int(input("Number of audio output channels (e.g. 2): "))

def select_midi_device():
    print("\n=== MIDI INPUT DEVICES ===")
    inputs = mido.get_input_names()
    for i, name in enumerate(inputs):
        print(f"{i}: {name}")
    index = int(input("Select MIDI input port index: "))
    return inputs[index]

def start_server(audio_index, nchnls=2):
    s = pyo.Server(nchnls=nchnls)
    s.setOutputDevice(audio_index)
    s.boot()
    s.start()
    return s


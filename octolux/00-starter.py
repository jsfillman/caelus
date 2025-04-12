import pyo
import mido
import threading

# === AUDIO SETUP ===
print("=== AUDIO DEVICES ===")
pyo.pa_list_devices()
audio_index = int(input("Select audio output device index: "))

# === SERVER ===
s = pyo.Server(nchnls=2)
s.setOutputDevice(audio_index)
s.boot()
s.start()

# === SYNTH SETUP ===
freq = pyo.Sig(0)
amp = pyo.Sig(0)
sine = pyo.Sine(freq=freq, mul=amp)
sine_l = pyo.Sine(freq=freq, mul=amp).out(chnl=0)
sine_r = pyo.Sine(freq=freq + 5, mul=amp).out(chnl=1)

# === MIDI HANDLER THREAD ===
def midi_loop(port_name):
    with mido.open_input(port_name) as port:
        print(f"Listening on {port_name}...")
        for msg in port:
            if msg.type == "note_on" and msg.velocity > 0:
                print(f"Note ON: {msg.note}, vel={msg.velocity}")
                freq.value = pyo.midiToHz(msg.note)
                amp.value = msg.velocity / 127.0 * 0.2
            elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                print(f"Note OFF: {msg.note}")
                amp.value = 0
            elif msg.type == "polytouch":
                print(f"Aftertouch: note={msg.note}, value={msg.value}")
                amp.value = msg.value / 127.0 * 0.3

# === MIDI SETUP ===
print("\n=== MIDO INPUT PORTS ===")
for i, name in enumerate(mido.get_input_names()):
    print(f"{i}: {name}")
port_index = int(input("Select MIDI input port index: "))
midi_name = mido.get_input_names()[port_index]

midi_thread = threading.Thread(target=midi_loop, args=(midi_name,))
midi_thread.daemon = True
midi_thread.start()

# === RUN ===
print("\nSynth running with Mido. Play notes on your MIDI controller.")
input("Press Enter to quit...\n")
s.stop()


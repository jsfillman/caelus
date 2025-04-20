from pythonosc.udp_client import SimpleUDPClient
import time

# === OSC Setup ===
osc_ip = "127.0.0.1"
osc_port = 5510
client = SimpleUDPClient(osc_ip, osc_port)

# === MIDI Note Helpers ===
def note_on(note, velocity=100):
    print(f"Note ON: {note}")
    client.send_message("/Nebulux/noteon", [note, velocity])

def note_off(note):
    print(f"Note OFF: {note}")
    client.send_message("/Nebulux/noteoff", [note])

# === Melody Test ===
melody = [60, 62, 64, 65, 67, 69, 71, 72]  # C major scale
for note in melody:
    note_on(note)
    time.sleep(0.3)
    note_off(note)
    time.sleep(0.1)

# === Chord Test (C major triad) ===
chord = [60, 64, 67]
for note in chord:
    note_on(note, 90)
time.sleep(1.0)
for note in chord:
    note_off(note)

print("\nTest complete.")


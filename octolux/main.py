# main.py
import pyo
import sys
import signal
import threading
from ui import run_ui
from setup import select_audio_device, select_midi_device, select_num_channels, start_server
from midi_handler import start_midi_listener, stop_midi_listener
from oscillator import Oscillator
from wavetables import WaveformBank


# Flag to track if the application is running
running = True
midi_thread = None

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

# NEW: Add stability control (0-20 cents)
stability_control = pyo.Sig(0)  # Default to 0 (no random detuning)

oscillators = []
for i in range(8):
    osc = Oscillator(freq, amp, vol, out_chnl=i, waveform_bank=waveform_bank, table_name="triangle")
    oscillators.append(osc)

def trigger_note(event_type, note, value):
    if not running:
        return
        
    if event_type == "note_on":
        print(f"Note ON: {note}, velocity: {value}")
        freq.value = pyo.midiToHz(note)
        amp.value = value / 127.0 * 0.2
        
        # NEW: Apply random detuning based on stability control to each oscillator
        stability_cents = stability_control.value
        if stability_cents > 0:
            detune_values = []
            for osc in oscillators:
                # Apply random detuning and collect the values for logging
                cents = osc.apply_stability_detune(stability_cents)
                detune_values.append(cents)
            print(f"Applied stability detuning (±{stability_cents:.2f} cents): {[f'{c:.2f}' for c in detune_values]}")
        
        # Trigger all oscillators
        for osc in oscillators:
            osc.env.play()
            
    elif event_type == "note_off":
        print(f"Note OFF: {note}")
        amp.value = 0
        for osc in oscillators:
            osc.env.stop()
            
    elif event_type == "polytouch":
        print(f"Poly AT: note {note}, value {value}")
        amp.value = value / 127.0 * 0.3
        
    elif event_type == "aftertouch":
        print(f"Channel AT: value {value}")
        amp.value = value / 127.0 * 0.3

# === MIDI CALLBACK ===
def on_midi(event_type, note, value):
    if running:
        trigger_note(event_type, note, value)

# === MIDI LISTENER ===
midi_thread = start_midi_listener(midi_port, on_midi)

# Define a cleanup function
def cleanup():
    global running
    print("Starting cleanup...")
    running = False
    
    # Stop MIDI listener
    stop_midi_listener()
    
    # Stop all active notes
    for osc in oscillators:
        osc.env.stop()
    
    # Wait a moment for any processing to finish
    import time
    time.sleep(0.1)
    
    print("Cleanup complete!")

# Set up signal handlers for graceful termination
def signal_handler(sig, frame):
    print(f"Caught signal {sig}, cleaning up...")
    cleanup()
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)  # Termination request

# === RUN UI ===
# Update the UI call to include the server and cleanup callback
run_ui(vol_control, oscillators, waveform_bank, stability_control, s, cleanup)

# We shouldn't get here if using the PyQt6 event loop, but just in case:
print("\nMain thread exiting...\n")
cleanup()
s.stop()

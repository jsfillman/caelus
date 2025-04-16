# main.py with save/load functionality
import pyo
import sys
import signal
import threading
import time
import math
import os
from ui import run_ui
from setup import select_audio_device, select_midi_device, select_num_channels, start_server
from midi_handler import start_midi_listener, stop_midi_listener
from oscillator import Oscillator
from wavetables import WaveformBank
from settings import save_patch, load_patch
from polyphony import PolyphonicVoice, VoiceManager

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

# Master volume control
vol_control = pyo.Sig(0.8)  # Start with reasonable level

# Add stability control (0-20 cents)
stability_control = pyo.Sig(0)  # Default to 0 (no random detuning)

# Add polyphony control (1-16 voices)
max_polyphony = 8  # Can be made adjustable in the UI

# Create voice manager
voice_manager = VoiceManager(max_polyphony, vol_control, waveform_bank, stability_control, nchnls)

# Load default patch if available
default_patch = "octolux_last_patch.yaml"
if os.path.exists(default_patch):
    load_patch(default_patch, voice_manager, vol_control, stability_control)
    print(f"Loaded default patch from {default_patch}")

# === MIDI CALLBACK ===
def on_midi(event_type, note, value):
    if not running:
        return
        
    if event_type == "note_on":
        voice_manager.note_on(note, value)
            
    elif event_type == "note_off":
        voice_manager.note_off(note)
            
    elif event_type == "polytouch":
        # Could implement per-voice aftertouch
        pass
        
    elif event_type == "aftertouch":
        # Could implement channel aftertouch affecting all voices
        pass

# === MIDI LISTENER ===
midi_thread = start_midi_listener(midi_port, on_midi)

# Define a cleanup function
def cleanup():
    global running
    print("Starting cleanup...")
    running = False
    
    # Save current settings to last_patch.yaml
    save_patch("octolux_last_patch.yaml", voice_manager, vol_control, stability_control)
    print("Saved current settings to octolux_last_patch.yaml")
    
    # Stop MIDI listener
    stop_midi_listener()
    
    # Stop all active notes
    voice_manager.all_notes_off()
    
    # Wait a moment for any processing to finish
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
run_ui(vol_control, voice_manager.voices[0].oscillators, waveform_bank, stability_control, s, voice_manager, cleanup)

# We shouldn't get here if using the PyQt6 event loop, but just in case:
print("\nMain thread exiting...\n")
cleanup()
s.stop()

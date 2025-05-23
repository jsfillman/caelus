#!/usr/bin/env python3

import time
from pythonosc import udp_client
import math

def midi_to_freq(midi_note):
    """Convert MIDI note number to frequency"""
    return 440.0 * math.pow(2.0, (midi_note - 69.0) / 12.0)

def play_note(client, freq, duration, synth_name="legato_synth_stereo"):
    """Play a note with the given frequency and duration"""
    # Send frequency first
    client.send_message(f"/{synth_name}/freq", freq)
    
    # Gate on
    client.send_message(f"/{synth_name}/gate", 1.0)
    
    # Wait for duration
    time.sleep(duration)
    
    # Gate off
    client.send_message(f"/{synth_name}/gate", 0.0)
    
    # Small gap between notes
    time.sleep(0.05)

def init_synth(client, synth_name="legato_synth_stereo"):
    """Initialize synth parameters"""
    # Set waveform to sawtooth
    client.send_message(f"/{synth_name}/wave_type", 2)
    
    # Set ADSR (moderate values)
    client.send_message(f"/{synth_name}/attack_L", 0.01)
    client.send_message(f"/{synth_name}/decay_L", 0.1)
    client.send_message(f"/{synth_name}/sustain_L", 0.7)
    client.send_message(f"/{synth_name}/release_L", 0.3)
    
    client.send_message(f"/{synth_name}/attack_R", 0.01)
    client.send_message(f"/{synth_name}/decay_R", 0.1)
    client.send_message(f"/{synth_name}/sustain_R", 0.7)
    client.send_message(f"/{synth_name}/release_R", 0.3)
    
    # Set filter cutoff high
    client.send_message(f"/{synth_name}/cutoff_L", 5000)
    client.send_message(f"/{synth_name}/cutoff_R", 5000)
    client.send_message(f"/{synth_name}/resonance_L", 0.5)
    client.send_message(f"/{synth_name}/resonance_R", 0.5)
    
    # Set gain
    client.send_message(f"/{synth_name}/gain", 0.7)

def main():
    # Create OSC client
    client = udp_client.SimpleUDPClient("127.0.0.1", 5510)
    synth_name = "legato_synth_stereo"
    
    # Initialize synth
    print("Initializing synth parameters...")
    init_synth(client, synth_name)
    time.sleep(0.5)  # Wait for parameters to settle
    
    # Define a simple melody (MIDI notes and durations in seconds)
    melody = [
        (60, 0.5),  # C4
        (64, 0.5),  # E4
        (67, 0.5),  # G4
        (72, 1.0),  # C5
        (67, 0.5),  # G4
        (64, 0.5),  # E4
        (60, 1.0),  # C4
    ]
    
    print("Playing melody...")
    
    # Play the melody
    for note, duration in melody:
        freq = midi_to_freq(note)
        print(f"Playing note: {note} (freq: {freq:.2f}Hz) for {duration}s")
        play_note(client, freq, duration, synth_name)
    
    print("Melody finished!")

if __name__ == "__main__":
    main() 
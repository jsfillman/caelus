#!/usr/bin/env python3

import socket
import time
import struct
import sys

def send_osc(ip, port, address, value):
    """Send a simple OSC message with a float value"""
    # Format OSC message
    address_bytes = address.encode('utf-8')
    # Pad to multiple of 4 bytes
    address_padded = address_bytes + (b'\0' * (4 - len(address_bytes) % 4 or 4))
    
    # Type tag
    type_tag = b',f'
    type_tag_padded = type_tag + (b'\0' * (4 - len(type_tag) % 4 or 4))
    
    # Value (float, big-endian)
    value_bytes = struct.pack('>f', float(value))
    
    # Complete message
    message = address_padded + type_tag_padded + value_bytes
    
    # Send via UDP
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(message, (ip, port))
    sock.close()
    print(f"Sent OSC: {address} = {value}")

def initialize_synth():
    """Set initial parameters for the complex synth"""
    # Main parameters
    send_osc("127.0.0.1", 5510, "/complex_synth/gain", 0.8)
    
    # Oscillator 1 (Sine, main oscillator)
    send_osc("127.0.0.1", 5510, "/complex_synth/osc1/waveform", 0)
    send_osc("127.0.0.1", 5510, "/complex_synth/osc1/level", 0.8)
    send_osc("127.0.0.1", 5510, "/complex_synth/osc1/octave", 0)
    
    # Oscillator 2 (Sawtooth, one octave up, slightly detuned)
    send_osc("127.0.0.1", 5510, "/complex_synth/osc2/waveform", 2)
    send_osc("127.0.0.1", 5510, "/complex_synth/osc2/level", 0.5)
    send_osc("127.0.0.1", 5510, "/complex_synth/osc2/octave", 1)
    send_osc("127.0.0.1", 5510, "/complex_synth/osc2/detune", 7)
    
    # Oscillator 3 (Square, one octave down)
    send_osc("127.0.0.1", 5510, "/complex_synth/osc3/waveform", 3)
    send_osc("127.0.0.1", 5510, "/complex_synth/osc3/level", 0.4)
    send_osc("127.0.0.1", 5510, "/complex_synth/osc3/octave", -1)
    send_osc("127.0.0.1", 5510, "/complex_synth/osc3/detune", -5)
    
    # Filter with moderate resonance
    send_osc("127.0.0.1", 5510, "/complex_synth/filter/cutoff", 2000)
    send_osc("127.0.0.1", 5510, "/complex_synth/filter/resonance", 0.4)
    
    # Envelope (moderate attack, decay, sustain, release)
    send_osc("127.0.0.1", 5510, "/complex_synth/env/attack", 0.05)
    send_osc("127.0.0.1", 5510, "/complex_synth/env/decay", 0.2)
    send_osc("127.0.0.1", 5510, "/complex_synth/env/sustain", 0.7)
    send_osc("127.0.0.1", 5510, "/complex_synth/env/release", 0.5)

def play_sequence():
    """Play a sequence of notes"""
    # Define a C major scale
    c_major = [261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88, 523.25]
    
    print("\nPlaying C major scale...")
    for freq in c_major:
        # Set frequency
        send_osc("127.0.0.1", 5510, "/complex_synth/freq", freq)
        
        # Note on
        send_osc("127.0.0.1", 5510, "/complex_synth/gate", 1.0)
        print(f"Note ON: {freq} Hz")
        
        # Hold note
        time.sleep(0.4)
        
        # Note off
        send_osc("127.0.0.1", 5510, "/complex_synth/gate", 0.0)
        print(f"Note OFF: {freq} Hz")
        
        # Pause between notes
        time.sleep(0.1)
    
    print("Sequence complete")

def play_with_filter_sweep():
    """Play a held note with a filter sweep"""
    # Set a sustained note
    send_osc("127.0.0.1", 5510, "/complex_synth/freq", 261.63)  # C4
    
    # Note on
    send_osc("127.0.0.1", 5510, "/complex_synth/gate", 1.0)
    print("\nPlaying sustained note with filter sweep...")
    
    # Sweep filter from low to high
    steps = 20
    for i in range(steps):
        cutoff = 100 + (i * 9000/steps)
        send_osc("127.0.0.1", 5510, "/complex_synth/filter/cutoff", cutoff)
        print(f"Filter cutoff: {cutoff:.1f} Hz")
        time.sleep(0.1)
    
    # Note off
    send_osc("127.0.0.1", 5510, "/complex_synth/gate", 0.0)
    print("Filter sweep complete")

def main():
    print("Complex Synth OSC Test")
    print("First, start the synth with: ./complex_synth --control 1")
    
    input("Press Enter when the synth is running...")
    
    try:
        print("\nInitializing synth parameters...")
        initialize_synth()
        
        # Play a simple sequence
        play_sequence()
        
        # Play a note with filter sweep
        play_with_filter_sweep()
        
        # Play another sequence
        play_sequence()
        
        print("\nTest complete!")
        
    except KeyboardInterrupt:
        # Turn off gate on exit
        send_osc("127.0.0.1", 5510, "/complex_synth/gate", 0.0)
        print("\nTest stopped.")

if __name__ == "__main__":
    main()
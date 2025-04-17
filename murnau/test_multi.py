#!/usr/bin/env python3
"""
Test script for multi_synth
"""
import socket
import time
import struct

def send_osc(ip, port, address, value):
    """Send an OSC message with a float value"""
    # Format OSC message
    address_bytes = address.encode('utf-8')
    address_padded = address_bytes + (b'\0' * (4 - len(address_bytes) % 4))
    
    # Format type tag
    type_tag = b',f'
    type_tag_padded = type_tag + (b'\0' * (4 - len(type_tag) % 4))
    
    # Format float value
    value_bytes = struct.pack('>f', float(value))
    
    # Complete message
    message = address_padded + type_tag_padded + value_bytes
    
    # Send via UDP
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(message, (ip, port))
    sock.close()
    print(f"Sent OSC: {address} = {value}")

def test_multi_synth():
    """Test multiple waveforms, filter and envelope settings"""
    synth_name = "multi_synth"
    ip = "127.0.0.1"
    port = 5510
    
    # Set default parameters - VERY AUDIBLE settings
    send_osc(ip, port, f"/{synth_name}/gain", 1.0)        # Maximum gain
    send_osc(ip, port, f"/{synth_name}/attack", 0.01)     # Immediate attack
    send_osc(ip, port, f"/{synth_name}/release", 0.8)     # Longer release
    send_osc(ip, port, f"/{synth_name}/cutoff", 10000)    # Wide open filter
    send_osc(ip, port, f"/{synth_name}/resonance", 0.2)   # Mild resonance
    
    # Test each waveform with and without filter
    waveforms = ["Sine", "Triangle", "Sawtooth", "Square"]
    
    for wave_idx, wave_name in enumerate(waveforms):
        # Set waveform
        send_osc(ip, port, f"/{synth_name}/wave_type", wave_idx)
        
        # Test without filter first
        print(f"\nTesting {wave_name} wave without filter")
        send_osc(ip, port, f"/{synth_name}/filter_on", 0)
        
        # Play a note
        play_note(ip, port, synth_name, 440.0, 0.5)  # A4
        
        # Test with filter
        print(f"\nTesting {wave_name} wave with filter")
        send_osc(ip, port, f"/{synth_name}/filter_on", 1)
        send_osc(ip, port, f"/{synth_name}/cutoff", 2000)
        send_osc(ip, port, f"/{synth_name}/resonance", 0.5)
        
        # Play a note
        play_note(ip, port, synth_name, 440.0, 0.5)
        
        # Filter sweep
        print(f"\nTesting {wave_name} wave with filter sweep")
        send_osc(ip, port, f"/{synth_name}/freq", 261.63)  # C4
        send_osc(ip, port, f"/{synth_name}/gate", 1.0)
        
        # Sweep filter from low to high
        for i in range(10):
            cutoff = 100 + (i * 1000)
            send_osc(ip, port, f"/{synth_name}/cutoff", cutoff)
            time.sleep(0.2)
        
        # Close gate
        send_osc(ip, port, f"/{synth_name}/gate", 0.0)
        time.sleep(0.5)

def play_note(ip, port, synth_name, freq, duration):
    """Helper to play a single note"""
    # Set frequency
    send_osc(ip, port, f"/{synth_name}/freq", freq)
    
    # Note on
    send_osc(ip, port, f"/{synth_name}/gate", 1.0)
    print(f"Note ON: {freq} Hz")
    
    # Hold note
    time.sleep(duration)
    
    # Note off
    send_osc(ip, port, f"/{synth_name}/gate", 0.0)
    print(f"Note OFF: {freq} Hz")
    
    # Wait for release
    time.sleep(0.4)

if __name__ == "__main__":
    print("Multi Synth Test")
    print("Start the synth with: ./multi_synth --control 1")
    print("And ensure it's connected to your audio outputs.")
    input("Press Enter when ready...")
    
    try:
        test_multi_synth()
        print("\nTest complete!")
    except KeyboardInterrupt:
        print("\nTest interrupted.")
        # Turn off gate
        send_osc("127.0.0.1", 5510, "/multi_synth/gate", 0.0)
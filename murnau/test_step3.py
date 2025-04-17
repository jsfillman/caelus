#!/usr/bin/env python3

"""
Test script for step3_waveforms synth
"""

import socket
import time
import struct

def send_osc(ip, port, address, value):
    """Send an OSC message with a float value"""
    # Format the address string with null bytes for padding
    address_bytes = address.encode('utf-8')
    address_padded = address_bytes + (b'\0' * (4 - len(address_bytes) % 4))
    
    # Format the type tag with null bytes for padding
    type_tag = b',f'
    type_tag_padded = type_tag + (b'\0' * (4 - len(type_tag) % 4))
    
    # Format the float value in big-endian
    value_bytes = struct.pack('>f', float(value))
    
    # Combine everything
    message = address_padded + type_tag_padded + value_bytes
    
    # Send the message via UDP
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(message, (ip, port))
    sock.close()
    print(f"Sent OSC: {address} = {value}")

def play_test():
    """Play test notes with different waveforms"""
    # Some parameters
    synth_name = "step3_waveforms"
    ip = "127.0.0.1"
    port = 5510
    
    # Set parameters
    send_osc(ip, port, f"/{synth_name}/gain", 1.0)
    send_osc(ip, port, f"/{synth_name}/cutoff", 5000)
    send_osc(ip, port, f"/{synth_name}/resonance", 0.3)
    
    # Use a moderate envelope
    send_osc(ip, port, f"/{synth_name}/attack", 0.05)
    send_osc(ip, port, f"/{synth_name}/decay", 0.1)
    send_osc(ip, port, f"/{synth_name}/sustain", 0.7)
    send_osc(ip, port, f"/{synth_name}/release", 0.3)
    
    # Define a C major chord
    notes = [261.63, 329.63, 392.00]  # C E G
    
    # Test each waveform
    waveforms = ["Sine", "Triangle", "Sawtooth", "Square"]
    
    for i, name in enumerate(waveforms):
        print(f"\nTesting waveform: {name}")
        
        # Set waveform
        send_osc(ip, port, f"/{synth_name}/wave_type", i)
        
        # Play each note with this waveform
        for freq in notes:
            # Set frequency
            send_osc(ip, port, f"/{synth_name}/freq", freq)
            
            # Note on
            send_osc(ip, port, f"/{synth_name}/gate", 1.0)
            print(f"Note ON: {freq} Hz")
            
            # Hold note
            time.sleep(0.5)
            
            # Note off
            send_osc(ip, port, f"/{synth_name}/gate", 0.0)
            print(f"Note OFF: {freq} Hz")
            
            # Wait for release to complete
            time.sleep(0.4)
    
    print("\nTest complete!")

if __name__ == "__main__":
    print("Step 3 Waveforms Test")
    print("Start the synth with: ./step3_waveforms --control 1")
    input("Press Enter when the synth is running...")
    
    try:
        play_test()
    except KeyboardInterrupt:
        print("\nTest interrupted.")
        # Turn off gate
        send_osc("127.0.0.1", 5510, "/step3_waveforms/gate", 0.0)
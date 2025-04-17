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

def test_synth():
    """Send test messages to the simplified complex synth"""
    synth_name = "simplified_complex"
    
    print("Setting parameters...")
    # Set parameters for maximum audibility
    send_osc("127.0.0.1", 5510, f"/{synth_name}/gain", 1.0)
    send_osc("127.0.0.1", 5510, f"/{synth_name}/cutoff", 5000)
    send_osc("127.0.0.1", 5510, f"/{synth_name}/resonance", 0.3)
    send_osc("127.0.0.1", 5510, f"/{synth_name}/attack", 0.01)
    send_osc("127.0.0.1", 5510, f"/{synth_name}/release", 0.5)
    
    # Try each waveform
    waveforms = ["Sine", "Triangle", "Sawtooth", "Square"]
    for i, name in enumerate(waveforms):
        print(f"\nTesting {name} wave...")
        send_osc("127.0.0.1", 5510, f"/{synth_name}/wave_type", i)
        
        # Play a note
        send_osc("127.0.0.1", 5510, f"/{synth_name}/freq", 440)  # A4
        send_osc("127.0.0.1", 5510, f"/{synth_name}/gate", 1.0)
        
        # Hold for 1 second
        time.sleep(1.0)
        
        # Release note
        send_osc("127.0.0.1", 5510, f"/{synth_name}/gate", 0.0)
        time.sleep(0.5)
    
    print("\nTest complete!")

if __name__ == "__main__":
    print("Simplified Complex Synth Test")
    print("Start the synth with: ./simplified_complex --control 1")
    input("Press Enter when the synth is running...")
    
    try:
        test_synth()
    except KeyboardInterrupt:
        print("\nTest stopped.")
        # Make sure gate is off
        send_osc("127.0.0.1", 5510, "/simplified_complex/gate", 0.0)
#!/usr/bin/env python3

"""
Test script for step1_filter synth
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
    """Play a test with filter parameter changes"""
    # Some parameters
    synth_name = "step1_filter"
    ip = "127.0.0.1"
    port = 5510
    
    # Set parameters
    send_osc(ip, port, f"/{synth_name}/gain", 1.0)
    send_osc(ip, port, f"/{synth_name}/cutoff", 5000)
    send_osc(ip, port, f"/{synth_name}/resonance", 0.3)
    
    # Play a note with changing filter cutoff
    freq = 440  # A4
    
    print("\nPlaying test note with filter sweep...")
    
    # Set frequency
    send_osc(ip, port, f"/{synth_name}/freq", freq)
    
    # Note on
    send_osc(ip, port, f"/{synth_name}/gate", 1.0)
    print(f"Note ON: {freq} Hz")
    
    # Hold note and sweep filter
    steps = 10
    for i in range(steps):
        cutoff = 100 + (i * 9900/steps)
        send_osc(ip, port, f"/{synth_name}/cutoff", cutoff)
        print(f"Filter cutoff: {cutoff} Hz")
        time.sleep(0.5)
    
    # Note off
    send_osc(ip, port, f"/{synth_name}/gate", 0.0)
    print(f"Note OFF: {freq} Hz")
    
    print("\nTest complete!")

if __name__ == "__main__":
    print("Step 1 Filter Test")
    print("Start the synth with: ./step1_filter --control 1")
    input("Press Enter when the synth is running...")
    
    try:
        play_test()
    except KeyboardInterrupt:
        print("\nTest interrupted.")
        # Turn off gate
        send_osc("127.0.0.1", 5510, "/step1_filter/gate", 0.0)
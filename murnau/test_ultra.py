#!/usr/bin/env python3

"""
Test script for ultra simple synth
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

def play_simple_test():
    """Play a test sequence with ultra_simple synth"""
    # Some parameters
    synth_name = "ultra_simple"
    ip = "127.0.0.1"
    port = 5510
    
    # Set maximum gain for clear audibility
    send_osc(ip, port, f"/{synth_name}/gain", 1.0)
    
    # Play a sequence of notes
    notes = [261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88, 523.25]
    
    print("\nPlaying C major scale...")
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
        
        # Pause between notes
        time.sleep(0.1)
    
    print("\nTest complete!")

if __name__ == "__main__":
    print("Ultra Simple Synth Test")
    print("Start the synth with: ./ultra_simple --control 1")
    input("Press Enter when the synth is running...")
    
    try:
        play_simple_test()
    except KeyboardInterrupt:
        print("\nTest interrupted.")
        # Turn off gate
        send_osc("127.0.0.1", 5510, "/ultra_simple/gate", 0.0)
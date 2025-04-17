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

def play_notes():
    """Play simple notes using OSC"""
    print("Sending notes to simple_osc synth...")
    print("Press Ctrl+C to exit")
    
    try:
        # Play a sequence of notes
        frequencies = [261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88, 523.25]
        
        while True:
            for freq in frequencies:
                # Set frequency
                send_osc("127.0.0.1", 5510, "/simple_osc/freq", freq)
                
                # Note on
                send_osc("127.0.0.1", 5510, "/simple_osc/gate", 1.0)
                print(f"Note ON: {freq} Hz")
                
                # Hold note
                time.sleep(0.3)
                
                # Note off
                send_osc("127.0.0.1", 5510, "/simple_osc/gate", 0.0)
                print(f"Note OFF: {freq} Hz")
                
                # Pause between notes
                time.sleep(0.1)
            
            print("Sequence complete, repeating...")
            time.sleep(0.5)
            
    except KeyboardInterrupt:
        # Turn off gate on exit
        send_osc("127.0.0.1", 5510, "/simple_osc/gate", 0.0)
        print("\nStopped.")

if __name__ == "__main__":
    print("Simple OSC Test for Faust")
    print("First, start the synth with: ./simple_osc --control 1")
    
    input("Press Enter when the synth is running...")
    play_notes()
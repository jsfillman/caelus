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
    """Play notes with different waveforms using OSC"""
    print("Sending notes to medium_synth synth...")
    print("Press Ctrl+C to exit")
    
    try:
        # Set envelope parameters
        send_osc("127.0.0.1", 5510, "/medium_synth/attack", 0.01)
        send_osc("127.0.0.1", 5510, "/medium_synth/release", 0.5)
        send_osc("127.0.0.1", 5510, "/medium_synth/gain", 0.8)
        
        # Play a sequence of notes with different waveforms
        frequencies = [261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88, 523.25]
        waveforms = [0, 1, 2, 3]  # sine, triangle, saw, square
        
        for wave in waveforms:
            print(f"\nSwitching to waveform {wave}")
            send_osc("127.0.0.1", 5510, "/medium_synth/wave_type", wave)
            
            for freq in frequencies:
                # Set frequency
                send_osc("127.0.0.1", 5510, "/medium_synth/freq", freq)
                
                # Note on
                send_osc("127.0.0.1", 5510, "/medium_synth/gate", 1.0)
                print(f"Note ON: {freq} Hz (waveform {wave})")
                
                # Hold note
                time.sleep(0.3)
                
                # Note off
                send_osc("127.0.0.1", 5510, "/medium_synth/gate", 0.0)
                print(f"Note OFF: {freq} Hz")
                
                # Pause between notes
                time.sleep(0.1)
            
            print(f"Sequence complete for waveform {wave}")
            time.sleep(0.5)
            
    except KeyboardInterrupt:
        # Turn off gate on exit
        send_osc("127.0.0.1", 5510, "/medium_synth/gate", 0.0)
        print("\nStopped.")

if __name__ == "__main__":
    print("Medium Synth OSC Test")
    print("First, start the synth with: ./medium_synth --control 1")
    
    input("Press Enter when the synth is running...")
    play_notes()
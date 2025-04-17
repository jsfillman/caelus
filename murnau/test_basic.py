#!/usr/bin/env python3
"""
Extremely basic test for basic_synth
Plays a repeated scale
"""
import socket
import time
import struct

def send_osc(ip, port, address, value):
    """Send an OSC message"""
    # Format message
    address_bytes = address.encode('utf-8')
    address_padded = address_bytes + (b'\0' * (4 - len(address_bytes) % 4))
    
    type_tag = b',f'
    type_tag_padded = type_tag + (b'\0' * (4 - len(type_tag) % 4))
    
    value_bytes = struct.pack('>f', float(value))
    
    message = address_padded + type_tag_padded + value_bytes
    
    # Send
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(message, (ip, port))
    sock.close()
    print(f"OSC: {address} = {value}")

def play_scale():
    """Play a repeating C major scale"""
    ip = "127.0.0.1"
    port = 5510
    
    # Set gain to maximum
    send_osc(ip, port, "/basic_synth/gain", 1.0)
    
    # C major scale frequencies
    frequencies = [261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88, 523.25]
    
    try:
        while True:
            print("\nPlaying C major scale...")
            for freq in frequencies:
                # Set frequency
                send_osc(ip, port, "/basic_synth/freq", freq)
                
                # Note on
                send_osc(ip, port, "/basic_synth/gate", 1.0)
                print(f"Playing note: {freq} Hz")
                
                # Hold note
                time.sleep(0.3)
                
                # Note off
                send_osc(ip, port, "/basic_synth/gate", 0.0)
                
                # Pause between notes
                time.sleep(0.1)
            
            # Pause between scales
            time.sleep(1.0)
            
    except KeyboardInterrupt:
        print("\nStopping...")
        # Make sure gate is off
        send_osc(ip, port, "/basic_synth/gate", 0.0)

if __name__ == "__main__":
    print("Basic Synth Test")
    print("Start the synth with: ./basic_synth --control 1")
    print("Connect to audio: jack_connect basic_synth:out_0 system:playback_1")
    print("                  jack_connect basic_synth:out_0 system:playback_2")
    input("Press Enter when ready...")
    
    play_scale()
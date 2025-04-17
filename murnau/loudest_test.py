#!/usr/bin/env python3
"""
MAXIMUM VOLUME test for multi_synth - simplest possible test
This script should produce the loudest, most obvious sound.
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

def loudest_test():
    """Play the loudest, most obvious test note"""
    synth_name = "multi_synth"
    ip = "127.0.0.1"
    port = 5510
    
    print("=== LOUDEST POSSIBLE TEST ===")
    print("This should generate a very obvious sound")
    
    # Set absolutely maximum audibility settings
    print("Setting maximum volume parameters...")
    send_osc(ip, port, f"/{synth_name}/gain", 1.0)
    send_osc(ip, port, f"/{synth_name}/wave_type", 3)  # Square wave (loudest)
    send_osc(ip, port, f"/{synth_name}/filter_on", 0)  # Filter OFF for max volume
    send_osc(ip, port, f"/{synth_name}/attack", 0.001) # Immediate attack
    send_osc(ip, port, f"/{synth_name}/release", 1.0)  # Long release
    
    # Play a low note (more audible on most systems)
    freq = 110.0  # A2 - low A
    
    print(f"\nPlaying LOUD {freq}Hz square wave...")
    send_osc(ip, port, f"/{synth_name}/freq", freq)
    send_osc(ip, port, f"/{synth_name}/gate", 1.0)
    
    # Hold for 3 seconds
    print("(holding for 3 seconds)")
    time.sleep(3.0)
    
    # Release
    send_osc(ip, port, f"/{synth_name}/gate", 0.0)
    print("Note released. Waiting for release to complete...")
    time.sleep(1.0)
    
    print("\nDid you hear anything? (y/n)")

if __name__ == "__main__":
    print("MAXIMUM VOLUME TEST")
    print("Start the synth with: ./multi_synth --control 1")
    print("Connect to audio: jack_connect multi_synth:out_0 system:playback_1")
    print("                  jack_connect multi_synth:out_0 system:playback_2")
    print("\nMAKE SURE YOUR SPEAKERS/HEADPHONES ARE ON AND VOLUME IS UP")
    input("Press Enter when ready...")
    
    try:
        loudest_test()
        response = input().strip().lower()
        if response == 'y':
            print("Great! Synth is working correctly.")
        else:
            print("\nTroubleshooting steps:")
            print("1. Check system volume")
            print("2. Check JACK connections: run 'jack_lsp -c'")
            print("3. Make sure synth is running with: './multi_synth --control 1'")
            print("4. Try a different audio output")
    except KeyboardInterrupt:
        print("\nTest interrupted.")
        send_osc("127.0.0.1", 5510, "/multi_synth/gate", 0.0)
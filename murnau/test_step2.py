#!/usr/bin/env python3

"""
Test script for step2_envelope synth
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
    """Play test notes with different envelope settings"""
    # Some parameters
    synth_name = "step2_envelope"
    ip = "127.0.0.1"
    port = 5510
    
    # Set parameters
    send_osc(ip, port, f"/{synth_name}/gain", 1.0)
    send_osc(ip, port, f"/{synth_name}/cutoff", 5000)
    send_osc(ip, port, f"/{synth_name}/resonance", 0.3)
    
    # Define a few test frequencies
    frequencies = [261.63, 329.63, 392.00, 523.25]  # C4, E4, G4, C5
    
    # Test different envelope settings
    envelopes = [
        {"name": "Pluck", "attack": 0.001, "decay": 0.1, "sustain": 0.3, "release": 0.1},
        {"name": "Slow Attack", "attack": 0.5, "decay": 0.1, "sustain": 0.8, "release": 0.5},
        {"name": "Long Release", "attack": 0.01, "decay": 0.2, "sustain": 0.6, "release": 2.0}
    ]
    
    for env in envelopes:
        print(f"\nTesting envelope: {env['name']}")
        
        # Set envelope parameters
        send_osc(ip, port, f"/{synth_name}/attack", env["attack"])
        send_osc(ip, port, f"/{synth_name}/decay", env["decay"])
        send_osc(ip, port, f"/{synth_name}/sustain", env["sustain"])
        send_osc(ip, port, f"/{synth_name}/release", env["release"])
        
        # Play each note with this envelope
        for freq in frequencies:
            # Set frequency
            send_osc(ip, port, f"/{synth_name}/freq", freq)
            
            # Note on
            send_osc(ip, port, f"/{synth_name}/gate", 1.0)
            print(f"Note ON: {freq} Hz")
            
            # Hold note
            hold_time = 0.5 + env["attack"]  # Adjust hold time based on attack
            time.sleep(hold_time)
            
            # Note off
            send_osc(ip, port, f"/{synth_name}/gate", 0.0)
            print(f"Note OFF: {freq} Hz")
            
            # Wait for release to complete
            release_wait = env["release"] * 1.5  # Wait a bit longer than the release time
            time.sleep(release_wait)
    
    print("\nTest complete!")

if __name__ == "__main__":
    print("Step 2 Envelope Test")
    print("Start the synth with: ./step2_envelope --control 1")
    input("Press Enter when the synth is running...")
    
    try:
        play_test()
    except KeyboardInterrupt:
        print("\nTest interrupted.")
        # Turn off gate
        send_osc("127.0.0.1", 5510, "/step2_envelope/gate", 0.0)
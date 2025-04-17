#!/usr/bin/env python3

"""
Test script for step4_multivoice synth
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
    """Play test notes with multiple voices"""
    # Some parameters
    synth_name = "step4_multivoice"
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
    
    # Define a C major scale
    scale = [261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88, 523.25]
    
    # Test scenarios
    test_scenarios = [
        {
            "name": "Both voices - Sawtooth",
            "waveform": 2,
            "voice1_level": 0.8,
            "voice1_detune": 0,
            "voice2_level": 0.8,
            "voice2_detune": 7
        },
        {
            "name": "Detuned Square waves",
            "waveform": 3,
            "voice1_level": 0.8,
            "voice1_detune": -5,
            "voice2_level": 0.8,
            "voice2_detune": 5
        },
        {
            "name": "Voice 1 only - Sine",
            "waveform": 0,
            "voice1_level": 1.0,
            "voice1_detune": 0,
            "voice2_level": 0.0,
            "voice2_detune": 0
        }
    ]
    
    for scenario in test_scenarios:
        print(f"\nTesting scenario: {scenario['name']}")
        
        # Set voice parameters
        send_osc(ip, port, f"/{synth_name}/wave_type", scenario["waveform"])
        send_osc(ip, port, f"/{synth_name}/voice1/level", scenario["voice1_level"])
        send_osc(ip, port, f"/{synth_name}/voice1/detune", scenario["voice1_detune"])
        send_osc(ip, port, f"/{synth_name}/voice2/level", scenario["voice2_level"])
        send_osc(ip, port, f"/{synth_name}/voice2/detune", scenario["voice2_detune"])
        
        # Play 4 notes from the scale
        for freq in scale[::2]:  # Take every other note
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
    print("Step 4 Multi-Voice Test")
    print("Start the synth with: ./step4_multivoice --control 1")
    input("Press Enter when the synth is running...")
    
    try:
        play_test()
    except KeyboardInterrupt:
        print("\nTest interrupted.")
        # Turn off gate
        send_osc("127.0.0.1", 5510, "/step4_multivoice/gate", 0.0)
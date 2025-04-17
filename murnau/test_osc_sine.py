#!/usr/bin/env python3
"""
Test OSC communication with sine_synth
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

def test_sine():
    """Play a simple test sequence"""
    synth_name = "sine_synth"
    ip = "127.0.0.1"
    port = 5510
    
    # Set maximum gain
    send_osc(ip, port, f"/{synth_name}/gain", 1.0)
    
    # Play a C major scale
    print("\nPlaying C major scale...")
    notes = [261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88, 523.25]
    
    for freq in notes:
        # Set frequency
        send_osc(ip, port, f"/{synth_name}/freq", freq)
        
        # Note on
        send_osc(ip, port, f"/{synth_name}/gate", 1.0)
        print(f"Note ON: {freq} Hz")
        
        # Hold note
        time.sleep(0.3)
        
        # Note off
        send_osc(ip, port, f"/{synth_name}/gate", 0.0)
        print(f"Note OFF: {freq} Hz")
        
        # Pause between notes
        time.sleep(0.1)
    
    print("\nTest complete!")

if __name__ == "__main__":
    print("Sine Synth OSC Test")
    print("Make sure to start the synth first with: ./sine_synth --control 1")
    print("And ensure it's connected to your audio outputs.")
    input("Press Enter when ready...")
    
    try:
        test_sine()
    except KeyboardInterrupt:
        print("\nTest interrupted.")
        # Turn off gate
        send_osc("127.0.0.1", 5510, "/sine_synth/gate", 0.0)
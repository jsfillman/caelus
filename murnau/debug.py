#!/usr/bin/env python3

"""
Debug the Faust synth by generating a simple test tone
using the Python-OSC library.
"""

import socket
import time
import struct
import sys

def send_raw_osc(host, port, address, value):
    """Send a simple OSC float message directly via UDP socket"""
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
    
    try:
        # Create UDP socket and send
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(message, (host, port))
        print(f"Sent OSC: {address} = {value}")
        
        # Optionally uncomment to see the raw bytes
        # print(f"Raw bytes: {message}")
        
        return True
    except Exception as e:
        print(f"Error sending OSC: {e}")
        return False
    finally:
        try:
            sock.close()
        except:
            pass

def generate_test_tone(host="127.0.0.1", port=5510):
    """Generate a simple test tone using the synth"""
    print("=== Faust Synth Debug - Test Tone Generator ===")
    print(f"Sending OSC messages to {host}:{port}")
    
    # Set parameters (loud, wide open filter)
    send_raw_osc(host, port, "/minimono/gain", 1.0)
    send_raw_osc(host, port, "/minimono/filter_cutoff", 10000)
    send_raw_osc(host, port, "/minimono/filter_resonance", 0.1)
    send_raw_osc(host, port, "/minimono/osc1_level", 1.0)
    send_raw_osc(host, port, "/minimono/osc2_level", 0.0)  # Turn off osc2
    send_raw_osc(host, port, "/minimono/osc3_level", 0.0)  # Turn off osc3
    
    # Set simple sine wave on osc1
    send_raw_osc(host, port, "/minimono/osc1_waveform", 0.0)  # Sine
    
    # Set instant attack/release for test
    send_raw_osc(host, port, "/minimono/amp_env_attack", 0.001)
    send_raw_osc(host, port, "/minimono/amp_env_decay", 0.001)
    send_raw_osc(host, port, "/minimono/amp_env_sustain", 1.0)
    send_raw_osc(host, port, "/minimono/amp_env_release", 0.001)
    
    # Play test
    print("\nGenerating test tone at 440 Hz (A4)...")
    print("Press Ctrl+C to stop")
    
    try:
        # Set frequency to A4 (440 Hz)
        send_raw_osc(host, port, "/minimono/freq", 440.0)
        
        # Turn gate on
        send_raw_osc(host, port, "/minimono/gate", 1.0)
        
        # Keep the note on until interrupted
        while True:
            time.sleep(0.5)
            # Periodically re-send gate on in case previous message was lost
            send_raw_osc(host, port, "/minimono/gate", 1.0)
            
    except KeyboardInterrupt:
        # Turn gate off
        send_raw_osc(host, port, "/minimono/gate", 0.0)
        print("\nTest tone stopped.")

if __name__ == "__main__":
    # Get port from command line if provided
    port = 5510
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port: {sys.argv[1]}")
            sys.exit(1)
    
    generate_test_tone(port=port)
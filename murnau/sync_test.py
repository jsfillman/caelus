#!/usr/bin/env python3

"""
Test to see if the synth's JACK client name matches what we expect
and if OSC ports are correctly configured.
"""

import socket
import time
import struct
import subprocess
import re

def check_jack_connections():
    """Check JACK connections and print them"""
    print("Checking JACK connections...")
    result = subprocess.run(['jack_lsp', '-c'], capture_output=True, text=True)
    print(result.stdout)
    
    # Check if minimono is connected to outputs
    if "minimono:out_0" in result.stdout and "system:playback" in result.stdout:
        print("✅ minimono is connected to system playback")
    else:
        print("❌ minimono is NOT properly connected to system playback")
        
        # Try to connect it
        print("Attempting to connect minimono to system playback...")
        subprocess.run(['jack_connect', 'minimono:out_0', 'system:playback_1'])
        subprocess.run(['jack_connect', 'minimono:out_0', 'system:playback_2'])
        
        # Check again
        result = subprocess.run(['jack_lsp', '-c'], capture_output=True, text=True)
        if "minimono:out_0" in result.stdout and "system:playback" in result.stdout:
            print("✅ Connection successful!")
        else:
            print("❌ Failed to connect minimono to system playback")

def check_minimono_process():
    """Check if minimono is running with OSC control"""
    print("Checking for running minimono process...")
    result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
    
    minimono_processes = [line for line in result.stdout.split('\n') if 'minimono' in line and '--control' in line]
    
    if minimono_processes:
        print("✅ Found minimono running with --control option:")
        for proc in minimono_processes:
            print(f"  {proc}")
    else:
        print("❌ No minimono process found with --control option")
        print("Please run: ./minimono --control 1")

def send_osc_message(ip, port, address, value):
    """Send a simple OSC message with a float value and return if it succeeded"""
    try:
        # Format address
        address_bytes = address.encode('utf-8')
        address_padded = address_bytes + (b'\0' * (4 - len(address_bytes) % 4 or 4))
        
        # Format type tag (f for float)
        type_tag = b',f'
        type_tag_padded = type_tag + (b'\0' * (4 - len(type_tag) % 4 or 4))
        
        # Format float value (big-endian)
        value_bytes = struct.pack('>f', float(value))
        
        # Combine all parts
        message = address_padded + type_tag_padded + value_bytes
        
        # Send via UDP
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(message, (ip, port))
        sock.close()
        print(f"Sent OSC: {address} = {value}")
        return True
    except Exception as e:
        print(f"❌ Failed to send OSC message: {e}")
        return False

def test_osc_communication():
    """Test OSC communication with the synth"""
    print("\nTesting OSC communication...")
    
    # Try sending to the OSC port
    success = send_osc_message("127.0.0.1", 5510, "/minimono/gain", 1.0)
    if success:
        print("✅ Successfully sent OSC message to port 5510")
    else:
        print("❌ Failed to send OSC message to port 5510")
    
    # Play a short test note
    print("\nPlaying a test note...")
    send_osc_message("127.0.0.1", 5510, "/minimono/freq", 440.0)
    send_osc_message("127.0.0.1", 5510, "/minimono/gate", 1.0)
    time.sleep(0.5)
    send_osc_message("127.0.0.1", 5510, "/minimono/gate", 0.0)
    
    print("\nDid you hear the test note? (y/n)")
    response = input().strip().lower()
    
    if response == 'y':
        print("✅ OSC communication is working correctly!")
    else:
        print("❌ OSC communication test failed - no sound was heard")
        print("Problems could be:")
        print("1. JACK audio routing")
        print("2. OSC port configuration")
        print("3. System volume")

def main():
    print("=== Minimono Synth Test and Diagnostics ===\n")
    
    # Check JACK connections
    check_jack_connections()
    
    # Check if minimono is running
    print("\n")
    check_minimono_process()
    
    # Test OSC communication
    test_osc_communication()
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3

import socket
import time
import struct

# Simple OSC test with much louder volume
def send_osc_message(ip, port, address, value):
    """Send a simple OSC message with a float value"""
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

def main():
    print("LOUD TEST - Testing with maximum volume")
    
    # Set maximum volume and very high cutoff
    send_osc_message("127.0.0.1", 5510, "/minimono/gain", 1.0)
    send_osc_message("127.0.0.1", 5510, "/minimono/filter_cutoff", 10000)
    send_osc_message("127.0.0.1", 5510, "/minimono/filter_resonance", 0.2)
    send_osc_message("127.0.0.1", 5510, "/minimono/osc1_level", 1.0)
    send_osc_message("127.0.0.1", 5510, "/minimono/osc2_level", 1.0)
    send_osc_message("127.0.0.1", 5510, "/minimono/osc3_level", 1.0)
    
    # Make a very pronounced envelope
    send_osc_message("127.0.0.1", 5510, "/minimono/amp_env_attack", 0.001)
    send_osc_message("127.0.0.1", 5510, "/minimono/amp_env_decay", 0.1)
    send_osc_message("127.0.0.1", 5510, "/minimono/amp_env_sustain", 1.0)
    send_osc_message("127.0.0.1", 5510, "/minimono/amp_env_release", 2.0)
    
    # Set a low note
    send_osc_message("127.0.0.1", 5510, "/minimono/freq", 110.0)  # A2
    
    # Play a long note
    print("Playing loud low A - should be very audible...")
    send_osc_message("127.0.0.1", 5510, "/minimono/gate", 1.0)
    time.sleep(2.0)
    send_osc_message("127.0.0.1", 5510, "/minimono/gate", 0.0)
    time.sleep(3.0)

if __name__ == "__main__":
    main()
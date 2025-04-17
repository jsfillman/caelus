#!/usr/bin/env python3

import socket
import time

# Simple OSC test without dependencies
def send_osc_message(ip, port, address, value):
    """Send a simple OSC message with a float value"""
    # OSC message format
    # - Address string (null-terminated)
    # - Type tag string (null-terminated, starts with ',')
    # - Value(s) aligned to 4-byte boundaries
    
    # Format address
    address_bytes = address.encode('utf-8')
    address_padded = address_bytes + (b'\0' * (4 - len(address_bytes) % 4 or 4))
    
    # Format type tag (f for float)
    type_tag = b',f'
    type_tag_padded = type_tag + (b'\0' * (4 - len(type_tag) % 4 or 4))
    
    # Format float value (big-endian)
    import struct
    value_bytes = struct.pack('>f', float(value))
    
    # Combine all parts
    message = address_padded + type_tag_padded + value_bytes
    
    # Send via UDP
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(message, (ip, port))
    sock.close()
    print(f"Sent OSC: {address} = {value}")

def main():
    print("Simple OSC Test without dependencies")
    print("Sending to 127.0.0.1:5510")
    
    try:
        # Play a C major scale
        frequencies = [261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88, 523.25]
        
        # Set initial parameters
        print("Setting initial parameters...")
        send_osc_message("127.0.0.1", 5510, "/minimono/gain", 0.8)
        send_osc_message("127.0.0.1", 5510, "/minimono/filter_cutoff", 2000)
        send_osc_message("127.0.0.1", 5510, "/minimono/filter_resonance", 0.6)
        send_osc_message("127.0.0.1", 5510, "/minimono/osc1_level", 0.8)
        send_osc_message("127.0.0.1", 5510, "/minimono/osc2_level", 0.6)
        send_osc_message("127.0.0.1", 5510, "/minimono/osc3_level", 0.4)
        
        print("Playing test sequence...")
        for freq in frequencies:
            # Set frequency
            send_osc_message("127.0.0.1", 5510, "/minimono/freq", freq)
            
            # Note on
            send_osc_message("127.0.0.1", 5510, "/minimono/gate", 1.0)
            print(f"Note ON: {freq} Hz")
            
            # Hold note
            time.sleep(0.3)
            
            # Note off
            send_osc_message("127.0.0.1", 5510, "/minimono/gate", 0.0)
            print(f"Note OFF: {freq} Hz")
            
            # Pause between notes
            time.sleep(0.1)
            
        print("Sequence complete.")
            
    except KeyboardInterrupt:
        print("\nStopping...")
        # Make sure gate is off
        send_osc_message("127.0.0.1", 5510, "/minimono/gate", 0.0)
        print("Done")

if __name__ == "__main__":
    main()
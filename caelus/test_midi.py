#!/usr/bin/env python3
"""
Simple MIDI test script to debug MIDI input issues
"""
import sys
import time
import mido

print("MIDI Test Script")
print("===============")

# Check available ports
try:
    ports = mido.get_input_names()
    print(f"Available MIDI input ports: {ports}")
    
    if not ports:
        print("ERROR: No MIDI input ports found!")
        print("Please check your MIDI device connections and try again.")
        sys.exit(1)
        
except Exception as e:
    print(f"ERROR listing MIDI ports: {e}")
    sys.exit(1)

# Ask user to select a port
if len(ports) == 1:
    port_name = ports[0]
    print(f"Auto-selecting only available port: {port_name}")
else:
    print("\nPlease select a MIDI port:")
    for i, port in enumerate(ports):
        print(f"{i+1}. {port}")
    
    choice = input("Enter port number: ")
    try:
        idx = int(choice) - 1
        if idx < 0 or idx >= len(ports):
            raise ValueError("Invalid selection")
        port_name = ports[idx]
    except ValueError:
        print("Invalid selection. Exiting.")
        sys.exit(1)

print(f"\nMonitoring MIDI input on {port_name}")
print("Play some notes or move controllers...")
print("(Press Ctrl+C to exit)")

try:
    with mido.open_input(port_name) as inport:
        print(f"Successfully opened {port_name}")
        print("Waiting for MIDI messages...")
        
        while True:
            for msg in inport.iter_pending():
                print(f"MIDI: {msg}")
            time.sleep(0.01)
            
except KeyboardInterrupt:
    print("\nExiting...")
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1) 
#!/usr/bin/env python3
"""
Absolute minimum MIDI-to-OSC bridge for basic_synth
"""
import mido
import threading
import time
import os
import signal
import sys
import socket
import struct

def send_osc(osc_ip, osc_port, address, value):
    """Ultra-simple OSC message sender"""
    # Format OSC message
    address_bytes = address.encode('utf-8')
    address_padded = address_bytes + (b'\0' * (4 - len(address_bytes) % 4))
    
    type_tag = b',f'
    type_tag_padded = type_tag + (b'\0' * (4 - len(type_tag) % 4))
    
    value_bytes = struct.pack('>f', float(value))
    
    message = address_padded + type_tag_padded + value_bytes
    
    # Send via UDP
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(message, (osc_ip, osc_port))
    sock.close()
    print(f"OSC: {address} = {value}")

def process_midi(port_name, osc_ip, osc_port):
    """Process MIDI messages in a simple loop"""
    print(f"Opening MIDI port: {port_name}")
    print(f"Sending OSC to: {osc_ip}:{osc_port}")
    
    # Set maximum gain
    send_osc(osc_ip, osc_port, "/basic_synth/gain", 1.0)
    
    try:
        with mido.open_input(port_name) as midi_port:
            print(f"Connected to MIDI port: {port_name}")
            print("Playing notes will generate sound. Press Ctrl+C to quit.")
            
            while True:
                # Process any pending messages
                for message in midi_port.iter_pending():
                    # Handle note on
                    if message.type == 'note_on' and message.velocity > 0:
                        # Convert MIDI note to frequency
                        freq = 440.0 * (2.0 ** ((message.note - 69) / 12.0))
                        
                        # Send OSC messages
                        send_osc(osc_ip, osc_port, "/basic_synth/freq", freq)
                        send_osc(osc_ip, osc_port, "/basic_synth/gate", 1.0)
                        
                        print(f"Note ON: {message.note} (freq: {freq:.2f} Hz)")
                        
                    # Handle note off
                    elif message.type == 'note_off' or (message.type == 'note_on' and message.velocity == 0):
                        send_osc(osc_ip, osc_port, "/basic_synth/gate", 0.0)
                        print(f"Note OFF")
                
                # Brief sleep
                time.sleep(0.001)
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Turn off gate before exiting
        send_osc(osc_ip, osc_port, "/basic_synth/gate", 0.0)
        print("Cleanup complete")

def main():
    # Fixed settings - absolute minimum
    osc_ip = "127.0.0.1"
    osc_port = 5510
    
    # List MIDI ports
    midi_inputs = mido.get_input_names()
    if not midi_inputs:
        print("No MIDI input ports available!")
        return
    
    print("Available MIDI input ports:")
    for i, name in enumerate(midi_inputs):
        print(f"  {i}: {name}")
    
    # Select port
    selection = None
    while selection is None:
        port_input = input("Select MIDI port number (or 'q' to quit): ").strip()
        if port_input.lower() in ('q', 'quit'):
            return
            
        try:
            idx = int(port_input)
            if 0 <= idx < len(midi_inputs):
                selection = midi_inputs[idx]
            else:
                print(f"Invalid port number. Please enter 0-{len(midi_inputs)-1}")
        except ValueError:
            print("Please enter a valid number")
    
    # Process MIDI
    process_midi(selection, osc_ip, osc_port)

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
MIDI debugging tool - shows all incoming MIDI messages
and sends simple OSC test notes periodically
"""
import mido
import argparse
import threading
import time
import os
import signal
import sys
import socket
import struct

def send_osc(ip, port, address, value):
    """Send an OSC message via UDP socket"""
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
    
    try:
        # Send via UDP
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(message, (ip, port))
        sock.close()
        print(f"OSC: {address} = {value}")
        return True
    except Exception as e:
        print(f"Error sending OSC: {e}")
        return False

def process_midi(port_name, osc_ip="127.0.0.1", osc_port=5510, synth_name="multi_synth"):
    """Process all MIDI messages and print them out"""
    print(f"Opening MIDI port: {port_name}")
    print(f"Will send OSC to: {osc_ip}:{osc_port}")
    print(f"For synth: {synth_name}")
    
    # Send initial OSC settings
    print("\nSetting initial parameters...")
    send_osc(osc_ip, osc_port, f"/{synth_name}/gain", 1.0)
    send_osc(osc_ip, osc_port, f"/{synth_name}/wave_type", 3)  # Square wave
    send_osc(osc_ip, osc_port, f"/{synth_name}/filter_on", 0)  # Filter off
    send_osc(osc_ip, osc_port, f"/{synth_name}/attack", 0.001)
    send_osc(osc_ip, osc_port, f"/{synth_name}/release", 1.0)
    
    running = True
    current_note = None
    
    # Start a thread to play test notes periodically
    def play_test_notes():
        """Play test notes every 10 seconds if no MIDI activity"""
        last_activity = time.time()
        while running:
            now = time.time()
            if now - last_activity > 10 and current_note is None:
                # Play a test note
                print("\n=== PLAYING TEST NOTE (no MIDI activity) ===")
                freq = 220.0  # A3
                send_osc(osc_ip, osc_port, f"/{synth_name}/freq", freq)
                send_osc(osc_ip, osc_port, f"/{synth_name}/gate", 1.0)
                time.sleep(1.0)
                send_osc(osc_ip, osc_port, f"/{synth_name}/gate", 0.0)
                last_activity = time.time()
            time.sleep(1.0)
    
    # Start test notes thread
    test_thread = threading.Thread(target=play_test_notes)
    test_thread.daemon = True
    test_thread.start()
    
    try:
        with mido.open_input(port_name) as midi_port:
            print(f"Connected to MIDI port: {port_name}")
            print("Waiting for MIDI messages. Press Ctrl+C to quit.")
            
            while running:
                for message in midi_port.iter_pending():
                    # Print raw MIDI message
                    print(f"\nMIDI: {message}")
                    
                    # Process note events
                    if message.type == 'note_on' and message.velocity > 0:
                        # Convert MIDI note to frequency (A4 = 69 = 440Hz)
                        freq = 440.0 * (2.0 ** ((message.note - 69) / 12.0))
                        current_note = message.note
                        
                        print(f"Converting note {message.note} to freq {freq:.2f}Hz")
                        
                        # Send OSC messages for this note
                        send_osc(osc_ip, osc_port, f"/{synth_name}/freq", freq)
                        send_osc(osc_ip, osc_port, f"/{synth_name}/gate", 1.0)
                        send_osc(osc_ip, osc_port, f"/{synth_name}/gain", message.velocity / 127.0)
                        
                    elif message.type == 'note_off' or (message.type == 'note_on' and message.velocity == 0):
                        if current_note == message.note or current_note is None:
                            current_note = None
                            send_osc(osc_ip, osc_port, f"/{synth_name}/gate", 0.0)
                    
                    # Process CC messages
                    elif message.type == 'control_change':
                        # Just print for now
                        print(f"CC{message.control}: {message.value}")
                    
                time.sleep(0.001)  # Small sleep to prevent CPU overuse
                
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Clean up
        running = False
        send_osc(osc_ip, osc_port, f"/{synth_name}/gate", 0.0)
        print("Cleanup complete")

def main():
    parser = argparse.ArgumentParser(description='MIDI Debug Tool')
    parser.add_argument('--osc-ip', default='127.0.0.1', help='OSC server IP')
    parser.add_argument('--osc-port', type=int, default=5510, help='OSC server port')
    parser.add_argument('--synth-name', default='multi_synth', help='Synth name for OSC prefix')
    args = parser.parse_args()
    
    # List available MIDI ports
    midi_inputs = mido.get_input_names()
    if not midi_inputs:
        print("No MIDI input ports available!")
        return
    
    print("Available MIDI input ports:")
    for i, name in enumerate(midi_inputs):
        print(f"  {i}: {name}")
    
    # Get MIDI port selection
    selection = None
    while selection is None:
        try:
            port_input = input("Select MIDI input port number (or 'q' to quit): ").strip()
            if port_input.lower() in ('q', 'quit', 'exit'):
                print("Exiting...")
                return
                
            try:
                idx = int(port_input)
                if 0 <= idx < len(midi_inputs):
                    selection = midi_inputs[idx]
                else:
                    print(f"Please enter a number between 0 and {len(midi_inputs)-1}")
            except ValueError:
                print("Please enter a valid number")
        except EOFError:
            print("\nInput terminated. Exiting...")
            return
    
    # Process MIDI
    process_midi(selection, args.osc_ip, args.osc_port, args.synth_name)

if __name__ == "__main__":
    main()
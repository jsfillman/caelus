#!/usr/bin/env python3
"""
Improved MIDI-to-OSC bridge for basic_synth
Better note tracking and transitions
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

def process_midi(port_name, osc_ip, osc_port, synth_name="basic_synth"):
    """Process MIDI messages with improved note tracking"""
    print(f"Opening MIDI port: {port_name}")
    print(f"Sending OSC to: {osc_ip}:{osc_port}")
    print(f"For synth: {synth_name}")
    
    # Set maximum gain
    send_osc(osc_ip, osc_port, f"/{synth_name}/gain", 1.0)
    
    # Track active notes - key is MIDI note number, value is frequency
    active_notes = {}
    
    # Current playing note
    current_note = None
    
    try:
        with mido.open_input(port_name) as midi_port:
            print(f"Connected to MIDI port: {port_name}")
            print("Playing notes will generate sound. Press Ctrl+C to quit.")
            
            while True:
                # Process any pending messages
                for message in midi_port.iter_pending():
                    # Print all MIDI messages for debugging
                    print(f"MIDI: {message}")
                    
                    # Handle note on
                    if message.type == 'note_on' and message.velocity > 0:
                        # Convert MIDI note to frequency
                        freq = 440.0 * (2.0 ** ((message.note - 69) / 12.0))
                        
                        # Add to active notes
                        active_notes[message.note] = freq
                        
                        # If we already have a note playing, turn it off first
                        if current_note is not None:
                            send_osc(osc_ip, osc_port, f"/{synth_name}/gate", 0.0)
                            # Small delay to ensure note off is processed
                            time.sleep(0.01)
                        
                        # Send OSC messages for the new note
                        send_osc(osc_ip, osc_port, f"/{synth_name}/freq", freq)
                        send_osc(osc_ip, osc_port, f"/{synth_name}/gate", 1.0)
                        
                        # Update current note
                        current_note = message.note
                        
                        print(f"Note ON: {message.note} (freq: {freq:.2f} Hz)")
                        
                    # Handle note off
                    elif message.type == 'note_off' or (message.type == 'note_on' and message.velocity == 0):
                        # Remove from active notes
                        if message.note in active_notes:
                            del active_notes[message.note]
                        
                        # Only send note off if this is the current note
                        if message.note == current_note:
                            # If we have other active notes, switch to the most recent one
                            if active_notes:
                                # Find the highest note (most recently pressed)
                                next_note = max(active_notes.keys())
                                next_freq = active_notes[next_note]
                                
                                # First gate off
                                send_osc(osc_ip, osc_port, f"/{synth_name}/gate", 0.0)
                                # Small delay
                                time.sleep(0.01)
                                # Set new frequency
                                send_osc(osc_ip, osc_port, f"/{synth_name}/freq", next_freq)
                                # Gate back on
                                send_osc(osc_ip, osc_port, f"/{synth_name}/gate", 1.0)
                                
                                # Update current note
                                current_note = next_note
                                
                                print(f"Switched to note: {next_note} (freq: {next_freq:.2f} Hz)")
                            else:
                                # No more active notes, turn off gate
                                send_osc(osc_ip, osc_port, f"/{synth_name}/gate", 0.0)
                                current_note = None
                                print(f"All notes OFF")
                        else:
                            print(f"Note OFF (not current): {message.note}")
                
                # Brief sleep
                time.sleep(0.001)
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Turn off gate before exiting
        send_osc(osc_ip, osc_port, f"/{synth_name}/gate", 0.0)
        print("Cleanup complete")

def main():
    # Fixed settings
    osc_ip = "127.0.0.1"
    osc_port = 5510
    synth_name = "basic_synth"
    
    # Allow custom synth name
    if len(sys.argv) > 1:
        synth_name = sys.argv[1]
    
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
    
    # Process MIDI with the selected port
    process_midi(selection, osc_ip, osc_port, synth_name)

if __name__ == "__main__":
    main()
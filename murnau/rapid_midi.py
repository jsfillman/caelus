#!/usr/bin/env python3
"""
Enhanced MIDI-to-OSC bridge for basic_synth
Optimized for rapid note transitions and legato playing
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
    """Fast OSC message sender"""
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
    """Process MIDI messages optimized for rapid transitions"""
    print(f"Opening MIDI port: {port_name}")
    print(f"Sending OSC to: {osc_ip}:{osc_port}")
    print(f"For synth: {synth_name}")
    
    # Set maximum gain
    send_osc(osc_ip, osc_port, f"/{synth_name}/gain", 1.0)
    
    # Key handling variables
    active_notes = {}             # All currently held notes
    current_note = None           # Currently sounding note
    last_note_off_time = 0        # Time of last note-off command
    
    # Fast on/off transition - just set frequency first, then gate
    def play_note(note, freq):
        nonlocal current_note
        
        # First set frequency (do this BEFORE gate on)
        send_osc(osc_ip, osc_port, f"/{synth_name}/freq", freq)
        
        # If gate is already on, we don't need to resend it (legato)
        if current_note is None:
            send_osc(osc_ip, osc_port, f"/{synth_name}/gate", 1.0)
            
        current_note = note
    
    try:
        with mido.open_input(port_name) as midi_port:
            print(f"Connected to MIDI port: {port_name}")
            print("Playing notes will generate sound. Press Ctrl+C to quit.")
            
            while True:
                # Get all pending messages at once
                messages = list(midi_port.iter_pending())
                
                # If we have multiple messages, identify note-on followed immediately by note-off
                # This is common in fast playing when notes overlap
                if len(messages) > 1:
                    for i in range(len(messages) - 1):
                        # Check for note-on followed by note-off of previous note
                        if (messages[i].type == 'note_on' and messages[i].velocity > 0 and
                            messages[i+1].type == 'note_off'):
                            print("Detected quick transition")
                
                # Process each message
                for message in messages:
                    # Print all MIDI messages for debugging
                    print(f"MIDI: {message}")
                    
                    # Handle note on
                    if message.type == 'note_on' and message.velocity > 0:
                        # Convert MIDI note to frequency
                        freq = 440.0 * (2.0 ** ((message.note - 69) / 12.0))
                        
                        # Store in active notes
                        active_notes[message.note] = freq
                        
                        # Play the note (sets freq then gate if needed)
                        play_note(message.note, freq)
                        
                        print(f"Note ON: {message.note} (freq: {freq:.2f} Hz)")
                        
                    # Handle note off
                    elif message.type == 'note_off' or (message.type == 'note_on' and message.velocity == 0):
                        # Remove from active notes
                        if message.note in active_notes:
                            del active_notes[message.note]
                        
                        # Only react if this is the current sounding note
                        if message.note == current_note:
                            # Try to find another active note
                            if active_notes:
                                # Find the highest note (most recently pressed)
                                next_note = max(active_notes.keys())
                                next_freq = active_notes[next_note]
                                
                                # Rapid transition - set frequency first, keep gate on
                                send_osc(osc_ip, osc_port, f"/{synth_name}/freq", next_freq)
                                current_note = next_note
                                
                                print(f"Quick switch to note: {next_note} (freq: {next_freq:.2f} Hz)")
                            else:
                                # No more active notes
                                send_osc(osc_ip, osc_port, f"/{synth_name}/gate", 0.0)
                                current_note = None
                                last_note_off_time = time.time()
                                print("All notes OFF")
                
                # Brief sleep to avoid CPU overload
                time.sleep(0.0005)  # Even shorter sleep for faster response
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
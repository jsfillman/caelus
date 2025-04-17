#!/usr/bin/env python3
"""
Final optimized MIDI-to-OSC bridge for legato_synth
Handles both spaced notes and rapid transitions
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

def process_midi(port_name, osc_ip, osc_port, synth_name="legato_synth"):
    """Process MIDI messages with best practices"""
    print(f"Opening MIDI port: {port_name}")
    print(f"Sending OSC to: {osc_ip}:{osc_port}")
    print(f"For synth: {synth_name}")
    
    # Set initial parameters
    print("Setting initial parameters...")
    send_osc(osc_ip, osc_port, f"/{synth_name}/gain", 1.0)
    send_osc(osc_ip, osc_port, f"/{synth_name}/wave_type", 2)  # sawtooth
    send_osc(osc_ip, osc_port, f"/{synth_name}/attack", 0.005)  # Fast but not instant
    send_osc(osc_ip, osc_port, f"/{synth_name}/decay", 0.1)
    send_osc(osc_ip, osc_port, f"/{synth_name}/sustain", 0.9)  # High sustain
    send_osc(osc_ip, osc_port, f"/{synth_name}/release", 0.5)  # Moderate release
    
    # Key handling variables
    active_notes = {}             # All currently held notes
    current_note = None           # Currently sounding note
    last_gate_off_time = 0        # Time of last gate off command
    
    # Threshold for legato transitions (seconds)
    LEGATO_THRESHOLD = 0.03       # 30ms - if notes are closer than this, use legato
    
    try:
        with mido.open_input(port_name) as midi_port:
            print(f"Connected to MIDI port: {port_name}")
            print("Playing notes will generate sound. Press Ctrl+C to quit.")
            
            while True:
                # Get all pending messages
                for message in midi_port.iter_pending():
                    # Print all MIDI messages for debugging
                    print(f"MIDI: {message}")
                    
                    # Handle note on
                    if message.type == 'note_on' and message.velocity > 0:
                        # Convert MIDI note to frequency
                        freq = 440.0 * (2.0 ** ((message.note - 69) / 12.0))
                        
                        # Add to active notes
                        active_notes[message.note] = freq
                        
                        # Determine if we should use legato mode
                        now = time.time()
                        use_legato = (current_note is not None and 
                                     (now - last_gate_off_time < LEGATO_THRESHOLD))
                        
                        # Set frequency first
                        send_osc(osc_ip, osc_port, f"/{synth_name}/freq", freq)
                        
                        # If not in legato mode or no current note, send gate on
                        if not use_legato or current_note is None:
                            send_osc(osc_ip, osc_port, f"/{synth_name}/gate", 1.0)
                            print(f"Note ON: {message.note} (freq: {freq:.2f} Hz)")
                        else:
                            print(f"Legato transition to: {message.note} (freq: {freq:.2f} Hz)")
                        
                        current_note = message.note
                        
                    # Handle note off
                    elif message.type == 'note_off' or (message.type == 'note_on' and message.velocity == 0):
                        # Remove from active notes
                        if message.note in active_notes:
                            del active_notes[message.note]
                        
                        # Only react if this is the current sounding note
                        if message.note == current_note:
                            # Check if we have other active notes
                            if active_notes:
                                # Find the highest note (usually most recently pressed)
                                next_note = max(active_notes.keys())
                                next_freq = active_notes[next_note]
                                
                                # Set the new frequency
                                send_osc(osc_ip, osc_port, f"/{synth_name}/freq", next_freq)
                                current_note = next_note
                                
                                print(f"Switched to note: {next_note} (freq: {next_freq:.2f} Hz)")
                            else:
                                # No more active notes, turn off gate
                                send_osc(osc_ip, osc_port, f"/{synth_name}/gate", 0.0)
                                last_gate_off_time = time.time()
                                current_note = None
                                print("All notes OFF")
                        else:
                            print(f"Ignored note off for inactive note: {message.note}")
                    
                    # Handle sustain pedal (CC 64)
                    elif message.type == 'control_change' and message.control == 64:
                        if message.value >= 64:  # Sustain on
                            # Could implement sustain logic here if needed
                            print("Sustain pedal ON")
                        else:  # Sustain off
                            print("Sustain pedal OFF")
                    
                    # Handle other CCs for synth parameters
                    elif message.type == 'control_change':
                        cc = message.control
                        norm_value = message.value / 127.0
                        
                        # Map CCs to synth parameters
                        if cc == 1:  # Mod wheel - waveform
                            wave = int(norm_value * 3.99)
                            send_osc(osc_ip, osc_port, f"/{synth_name}/wave_type", wave)
                            wave_names = ["sine", "triangle", "saw", "square"]
                            print(f"Waveform: {wave_names[wave]}")
                        
                        elif cc == 73:  # Attack
                            attack = 0.001 + (norm_value * 0.999)
                            send_osc(osc_ip, osc_port, f"/{synth_name}/attack", attack)
                            print(f"Attack: {attack:.3f}s")
                        
                        elif cc == 75:  # Decay
                            decay = 0.001 + (norm_value * 0.999)
                            send_osc(osc_ip, osc_port, f"/{synth_name}/decay", decay)
                            print(f"Decay: {decay:.3f}s")
                        
                        elif cc == 31:  # Sustain
                            send_osc(osc_ip, osc_port, f"/{synth_name}/sustain", norm_value)
                            print(f"Sustain: {norm_value:.2f}")
                        
                        elif cc == 72:  # Release
                            release = 0.1 + (norm_value * 1.9)
                            send_osc(osc_ip, osc_port, f"/{synth_name}/release", release)
                            print(f"Release: {release:.2f}s")
                
                # Brief sleep to avoid CPU overload
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
    synth_name = "legato_synth"
    
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
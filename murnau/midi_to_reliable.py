#!/usr/bin/env python3
"""
Simplified MIDI-to-OSC bridge for reliable_synth
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

class MidiToOSC:
    def __init__(self, osc_ip="127.0.0.1", osc_port=5510, synth_name="reliable_synth"):
        self.osc_ip = osc_ip
        self.osc_port = osc_port
        self.synth_name = synth_name
        self.running = True
        
        # Initialize with reliable settings
        print("Setting initial parameters...")
        self.send_osc("gain", 1.0)
        self.send_osc("wave_type", 2)  # sawtooth
        self.send_osc("attack", 0.01)
        self.send_osc("release", 0.3)
        
    def send_osc(self, address, value):
        """Simple OSC message sender"""
        full_address = f"/{self.synth_name}/{address}"
        
        # Format OSC message
        address_bytes = full_address.encode('utf-8')
        address_padded = address_bytes + (b'\0' * (4 - len(address_bytes) % 4))
        
        type_tag = b',f'
        type_tag_padded = type_tag + (b'\0' * (4 - len(type_tag) % 4))
        
        value_bytes = struct.pack('>f', float(value))
        
        message = address_padded + type_tag_padded + value_bytes
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(message, (self.osc_ip, self.osc_port))
            sock.close()
            print(f"OSC: {full_address} = {value}")
        except Exception as e:
            print(f"Error sending OSC: {e}")
            
    def handle_midi_message(self, message):
        """Handle incoming MIDI message"""
        # Print all messages for debugging
        print(f"MIDI: {message}")
        
        if message.type == 'note_on' and message.velocity > 0:
            # Note on - convert to frequency
            freq = 440.0 * (2.0 ** ((message.note - 69) / 12.0))
            self.send_osc("freq", freq)
            self.send_osc("gate", 1.0)
            # Also set gain based on velocity
            self.send_osc("gain", message.velocity / 127.0)
            print(f"Note ON: {message.note} ({freq:.2f} Hz)")
            
        elif message.type == 'note_off' or (message.type == 'note_on' and message.velocity == 0):
            # Note off - just turn off gate
            self.send_osc("gate", 0.0)
            print(f"Note OFF")
            
        elif message.type == 'control_change':
            # CC handling - simplified
            cc = message.control
            value = message.value / 127.0  # normalize to 0-1
            
            if cc == 1:  # Mod wheel - use for waveform type
                wave = int(value * 3.99)  # 0-3 range
                self.send_osc("wave_type", wave)
                wave_names = ["sine", "triangle", "saw", "square"]
                print(f"Changed waveform to {wave_names[wave]}")
            
            elif cc == 73:  # Attack time
                attack = 0.001 + (value * 2.0)
                self.send_osc("attack", attack)
                
            elif cc == 72:  # Release time
                release = 0.05 + (value * 2.0)
                self.send_osc("release", release)
            
            # Print for any CC
            print(f"CC{cc}: {message.value}/127 = {value:.2f}")

    def cleanup(self):
        """Clean up before exit"""
        print("Cleaning up...")
        self.send_osc("gate", 0.0)
        self.running = False

def process_midi(converter, port_name):
    """Process MIDI in a separate thread"""
    try:
        with mido.open_input(port_name) as midi_port:
            print(f"Successfully connected to MIDI port: {port_name}")
            
            while converter.running:
                # Process any pending messages
                for message in midi_port.iter_pending():
                    if not converter.running:
                        break
                    converter.handle_midi_message(message)
                
                # Brief sleep to avoid CPU thrashing
                time.sleep(0.001)
    except Exception as e:
        print(f"Error in MIDI processing: {e}")
        converter.running = False

def main():
    parser = argparse.ArgumentParser(description='Simplified MIDI to OSC for reliable_synth')
    parser.add_argument('--osc-ip', default='127.0.0.1', help='OSC server IP')
    parser.add_argument('--osc-port', type=int, default=5510, help='OSC server port')
    args = parser.parse_args()
    
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
    
    # Create converter
    converter = MidiToOSC(args.osc_ip, args.osc_port)
    
    print(f"Using MIDI port: {selection}")
    print(f"Sending OSC to: {args.osc_ip}:{args.osc_port}")
    print("Ready for MIDI input. Press Ctrl+C to quit.")
    
    # Start MIDI thread
    midi_thread = threading.Thread(target=process_midi, args=(converter, selection))
    midi_thread.daemon = True
    midi_thread.start()
    
    # Wait for keyboard interrupt
    try:
        while converter.running:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        converter.cleanup()

if __name__ == "__main__":
    main()
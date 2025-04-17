#!/usr/bin/env python3
"""
Minimal MIDI to OSC bridge for sine_synth
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
    def __init__(self, osc_ip="127.0.0.1", osc_port=5510, synth_name="sine_synth"):
        self.osc_ip = osc_ip
        self.osc_port = osc_port
        self.synth_name = synth_name
        self.running = True
        self.active_notes = set()  # Track active notes for cleanup
        
        # Initialize gain
        self.send_osc("gain", 0.8)
        
    def send_osc(self, address, value):
        """Send an OSC message via UDP socket"""
        full_address = f"/{self.synth_name}/{address}"
        
        # Format OSC message
        address_bytes = full_address.encode('utf-8')
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
            sock.sendto(message, (self.osc_ip, self.osc_port))
            sock.close()
            print(f"OSC: {full_address} = {value}")
        except Exception as e:
            print(f"Error sending OSC: {e}")

    def handle_midi_message(self, message):
        """Process MIDI message and convert to OSC"""
        if message.type == 'note_on' and message.velocity > 0:
            # Convert MIDI note to frequency (A4 = 69 = 440Hz)
            freq = 440.0 * (2.0 ** ((message.note - 69) / 12.0))
            
            # Send frequency and gate
            self.send_osc("freq", freq)
            self.send_osc("gate", 1.0)
            
            # Also send velocity as gain
            self.send_osc("gain", message.velocity / 127.0)
            
            # Store active note
            self.active_notes.add(message.note)
            
            print(f"Note ON: {message.note} (freq: {freq:.2f} Hz)")
            
        elif message.type == 'note_off' or (message.type == 'note_on' and message.velocity == 0):
            # Turn off gate
            self.send_osc("gate", 0.0)
            
            # Remove from active notes
            if message.note in self.active_notes:
                self.active_notes.remove(message.note)
                
            print(f"Note OFF: {message.note}")

    def cleanup(self):
        """Ensure all notes are turned off"""
        print("Cleaning up...")
        self.send_osc("gate", 0.0)
        self.running = False
        print("Cleanup complete")

def process_midi(converter, port_name):
    """Process MIDI in a separate thread"""
    try:
        with mido.open_input(port_name) as midi_port:
            print(f"Connected to MIDI port: {port_name}")
            
            while converter.running:
                for message in midi_port.iter_pending():
                    if not converter.running:
                        break
                    converter.handle_midi_message(message)
                time.sleep(0.001)  # Small sleep to prevent CPU overuse
    except Exception as e:
        print(f"Error in MIDI processing: {e}")
        converter.running = False

def main():
    parser = argparse.ArgumentParser(description='Simple MIDI to OSC converter')
    parser.add_argument('--osc-ip', default='127.0.0.1', help='OSC server IP')
    parser.add_argument('--osc-port', type=int, default=5510, help='OSC server port')
    parser.add_argument('--synth-name', default='sine_synth', help='Synth name for OSC prefix')
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
    
    # Create converter
    converter = MidiToOSC(args.osc_ip, args.osc_port, args.synth_name)
    
    print(f"Using MIDI port: {selection}")
    print(f"Sending OSC to: {args.osc_ip}:{args.osc_port}")
    print(f"Using synth: {args.synth_name}")
    print("Ready for MIDI input. Press Ctrl+C to quit.")
    
    # Start MIDI processing thread
    midi_thread = threading.Thread(target=process_midi, args=(converter, selection))
    midi_thread.daemon = True
    midi_thread.start()
    
    # Handle clean termination
    def signal_handler(sig, frame):
        print("\nReceived termination signal. Cleaning up...")
        converter.cleanup()
        sys.exit(0)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Wait for MIDI thread
    try:
        midi_thread.join()
    except KeyboardInterrupt:
        pass
    finally:
        converter.cleanup()

if __name__ == "__main__":
    main()
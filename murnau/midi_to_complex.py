#!/usr/bin/env python3
"""
MIDI-to-OSC bridge for complex_synth
"""
import mido
import argparse
import threading
import time
import subprocess
import os
import signal
import sys
import socket
import struct

class MidiToOSC:
    def __init__(self, osc_ip="127.0.0.1", osc_port=5510, synth_name="complex_synth"):
        # OSC client setup
        self.osc_ip = osc_ip
        self.osc_port = osc_port
        self.synth_name = synth_name
        self.running = True
        self.active_notes = set()  # Keep track of active notes for cleanup
        
        # Initialize synth parameters
        print("Setting initial synth parameters...")
        self.initialize_synth()
        
    def initialize_synth(self):
        """Set initial parameters for the synth"""
        # Main parameters
        self.send_osc("gain", 0.8)
        
        # Oscillator 1 (Sine, main oscillator)
        self.send_osc("osc1/waveform", 0)
        self.send_osc("osc1/level", 0.8)
        self.send_osc("osc1/octave", 0)
        
        # Oscillator 2 (Sawtooth, one octave up, slightly detuned)
        self.send_osc("osc2/waveform", 2)
        self.send_osc("osc2/level", 0.5)
        self.send_osc("osc2/octave", 1)
        self.send_osc("osc2/detune", 7)
        
        # Oscillator 3 (Square, one octave down)
        self.send_osc("osc3/waveform", 3)
        self.send_osc("osc3/level", 0.4)
        self.send_osc("osc3/octave", -1)
        self.send_osc("osc3/detune", -5)
        
        # Filter with moderate resonance
        self.send_osc("filter/cutoff", 2000)
        self.send_osc("filter/resonance", 0.4)
        
        # Envelope (moderate attack, decay, sustain, release)
        self.send_osc("env/attack", 0.05)
        self.send_osc("env/decay", 0.2)
        self.send_osc("env/sustain", 0.7)
        self.send_osc("env/release", 0.5)

    def send_osc(self, address, value):
        """Send an OSC message to the synth"""
        # Construct the full address with synth name prefix
        full_address = f"/{self.synth_name}/{address}"
        
        # Format OSC message
        address_bytes = full_address.encode('utf-8')
        # Pad to multiple of 4 bytes
        address_padded = address_bytes + (b'\0' * (4 - len(address_bytes) % 4 or 4))
        
        # Type tag
        type_tag = b',f'
        type_tag_padded = type_tag + (b'\0' * (4 - len(type_tag) % 4 or 4))
        
        # Value (float, big-endian)
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
        """Process incoming MIDI messages and convert to OSC"""
        if message.type == 'note_on' and message.velocity > 0:
            # Convert MIDI note to frequency (A4 = 69 = 440Hz)
            freq = 440.0 * (2.0 ** ((message.note - 69) / 12.0))
            
            # Send frequency first, then gate
            self.send_osc("freq", freq)
            self.send_osc("gate", 1.0)
            
            # Also use velocity to control volume
            velocity_gain = message.velocity / 127.0
            self.send_osc("gain", velocity_gain * 0.8)
            
            # Store the active note
            self.active_notes.add(message.note)
            
            print(f"Note ON: {message.note} (freq: {freq:.2f} Hz, velocity: {message.velocity})")
            
        elif message.type == 'note_off' or (message.type == 'note_on' and message.velocity == 0):
            # For note off, just turn off the gate
            self.send_osc("gate", 0.0)
            
            # Remove from active notes
            if message.note in self.active_notes:
                self.active_notes.remove(message.note)
                
            print(f"Note OFF: {message.note}")
            
        elif message.type == 'control_change':
            # Map common MIDI CC numbers to synth parameters
            cc_value = message.value / 127.0  # Normalize to 0-1
            
            # Map based on CC number
            if message.control == 1:  # Mod wheel - filter cutoff
                cutoff = 100 + (cc_value * 10000)
                self.send_osc("filter/cutoff", cutoff)
                print(f"CC1 (Mod Wheel): {cc_value:.2f} -> filter cutoff {cutoff:.1f}Hz")
                
            elif message.control == 74:  # CC74 - filter cutoff (alternate)
                cutoff = 100 + (cc_value * 10000)
                self.send_osc("filter/cutoff", cutoff)
                
            elif message.control == 71:  # CC71 - filter resonance
                # Scale to 0-0.95 to avoid self-oscillation
                self.send_osc("filter/resonance", cc_value * 0.95)
                
            elif message.control == 73:  # CC73 - attack time
                attack = 0.001 + (cc_value * 2.0)
                self.send_osc("env/attack", attack)
                
            elif message.control == 75:  # CC75 - decay time
                decay = 0.001 + (cc_value * 2.0)
                self.send_osc("env/decay", decay)
                
            elif message.control == 79:  # CC79 - sustain level
                self.send_osc("env/sustain", cc_value)
                
            elif message.control == 72:  # CC72 - release time
                release = 0.001 + (cc_value * 4.0)
                self.send_osc("env/release", release)
                
            # Oscillator mix controls
            elif message.control == 20:  # CC20 - Osc1 level
                self.send_osc("osc1/level", cc_value)
                
            elif message.control == 21:  # CC21 - Osc2 level
                self.send_osc("osc2/level", cc_value)
                
            elif message.control == 22:  # CC22 - Osc3 level
                self.send_osc("osc3/level", cc_value)
                
            elif message.control == 23:  # CC23 - Osc2 detune
                detune = -50 + (cc_value * 100)  # Range from -50 to +50
                self.send_osc("osc2/detune", detune)
                
            elif message.control == 24:  # CC24 - Osc3 detune
                detune = -50 + (cc_value * 100)  # Range from -50 to +50
                self.send_osc("osc3/detune", detune)
                
            else:
                print(f"CC: control={message.control}, value={message.value}")

    def cleanup(self):
        """Ensure all notes are turned off"""
        print("Cleaning up...")
        self.send_osc("gate", 0.0)
        self.running = False
        print("Cleanup complete")

def launch_faust_synth(synth_path="./complex_synth", with_control=True):
    """Launch the Faust synthesizer as a subprocess"""
    command = f"{synth_path}"
    if with_control:
        command += " --control 1"
        
    print(f"Launching Faust synth: {command}")
    
    # Start synth as a subprocess
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            shell=True,
            bufsize=1
        )
        
        # Wait a moment for the synth to initialize
        print("Waiting for synth to initialize...")
        time.sleep(2)
        
        # Check if process is still running
        if process.poll() is not None:
            print(f"Error: Synth process exited with code {process.poll()}")
            return None
            
        print("Faust synth started successfully!")
        return process
        
    except Exception as e:
        print(f"Error launching synth: {e}")
        return None

def process_midi(converter, port_name):
    """Process MIDI messages in a separate thread"""
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
    parser = argparse.ArgumentParser(description='MIDI to OSC converter for complex_synth')
    parser.add_argument('--osc-ip', default='127.0.0.1', help='OSC server IP address')
    parser.add_argument('--osc-port', type=int, default=5510, help='OSC server port')
    parser.add_argument('--synth-name', default='complex_synth', 
                      help='Synth name (used as prefix for OSC messages)')
    parser.add_argument('--synth-path', default='./complex_synth',
                      help='Path to the Faust synth executable')
    parser.add_argument('--no-launch', action='store_true',
                      help='Do not launch the Faust synth (assume it is already running)')
    args = parser.parse_args()
    
    # Launch Faust synth if requested
    synth_process = None
    if not args.no_launch:
        synth_process = launch_faust_synth(args.synth_path)
        if not synth_process:
            print("Failed to launch Faust synth. Exiting.")
            return
    
    # List available MIDI ports
    midi_inputs = mido.get_input_names()
    if not midi_inputs:
        print("No MIDI input ports available!")
        if synth_process:
            synth_process.terminate()
        return
    
    print("Available MIDI input ports:")
    for i, name in enumerate(midi_inputs):
        print(f"  {i}: {name}")
    
    # Get MIDI port selection with validation
    selection = None
    while selection is None:
        try:
            port_input = input("Select MIDI input port number (or 'q' to quit): ").strip()
            if port_input.lower() in ('q', 'quit', 'exit'):
                print("Exiting...")
                if synth_process:
                    synth_process.terminate()
                return
                
            try:
                idx = int(port_input)
                if 0 <= idx < len(midi_inputs):
                    # Try to open the port to verify it's available
                    try:
                        with mido.open_input(midi_inputs[idx]) as test_port:
                            selection = midi_inputs[idx]
                    except Exception as e:
                        print(f"Error opening MIDI port: {e}")
                        print("Please try another port or make sure the device is connected.")
                else:
                    print(f"Please enter a number between 0 and {len(midi_inputs)-1}")
            except ValueError:
                print("Please enter a valid number")
        except EOFError:
            # Handle Ctrl+D
            print("\nInput terminated. Exiting...")
            if synth_process:
                synth_process.terminate()
            return
    
    # Create converter
    converter = MidiToOSC(args.osc_ip, args.osc_port, args.synth_name)
    
    print(f"Using MIDI port: {selection}")
    print(f"Sending OSC to: {args.osc_ip}:{args.osc_port}")
    print(f"Using synth: {args.synth_name}")
    print("Ready for MIDI input. Press Ctrl+C to quit.")
    
    # Start MIDI processing in a separate thread
    midi_thread = threading.Thread(target=process_midi, args=(converter, selection))
    midi_thread.daemon = True
    midi_thread.start()
    
    # Handle clean termination
    def signal_handler(sig, frame):
        print("\nReceived termination signal. Cleaning up...")
        converter.cleanup()
        if synth_process:
            print("Stopping Faust synth...")
            synth_process.terminate()
            try:
                synth_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print("Synth didn't terminate gracefully, forcing...")
                synth_process.kill()
        sys.exit(0)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Termination
    
    # Wait for MIDI thread to complete
    try:
        midi_thread.join()
    except KeyboardInterrupt:
        pass
    finally:
        # Clean up
        converter.cleanup()
        if synth_process:
            print("Stopping Faust synth...")
            synth_process.terminate()
            try:
                synth_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print("Synth didn't terminate gracefully, forcing...")
                synth_process.kill()

if __name__ == "__main__":
    main()
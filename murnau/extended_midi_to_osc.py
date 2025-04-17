#!/usr/bin/env python3
import mido
import argparse
import threading
import time
import subprocess
import os
import signal
import sys
import json
from pythonosc import udp_client

class MidiToOSC:
    def __init__(self, osc_ip="127.0.0.1", osc_port=5510, synth_name="minimono"):
        # OSC client setup
        self.osc_client = udp_client.SimpleUDPClient(osc_ip, osc_port)
        self.synth_name = synth_name
        self.running = True
        self.active_notes = set()  # Keep track of active notes for cleanup
        
        # Load OSC parameter mapping from synth JSON if available
        self.osc_params = self.load_synth_params(f"{synth_name}.dsp.json")
        
        print(f"Initialized with synth: {synth_name}")
        if self.osc_params:
            print(f"Loaded {len(self.osc_params)} OSC parameters")
        else:
            print("No synth parameters loaded. Using default mapping.")

    def load_synth_params(self, json_file):
        """Load OSC parameters from Faust-generated JSON file"""
        try:
            if os.path.exists(json_file):
                with open(json_file, 'r') as f:
                    data = json.load(f)
                
                # Extract OSC paths from UI elements
                params = {}
                if 'ui' in data:
                    self._extract_osc_params(data['ui'], params)
                return params
            else:
                print(f"Warning: Synth JSON file not found: {json_file}")
                return None
        except Exception as e:
            print(f"Error loading synth parameters: {e}")
            return None
    
    def _extract_osc_params(self, ui_elements, params, path=""):
        """Recursively extract OSC parameters from UI elements"""
        for elem in ui_elements:
            if elem.get('type') == 'vgroup' or elem.get('type') == 'hgroup' or elem.get('type') == 'tgroup':
                # Process groups recursively
                group_path = f"{path}/{elem['label']}" if path else elem['label']
                self._extract_osc_params(elem.get('items', []), params, group_path)
            elif 'address' in elem:
                # Extract OSC address
                full_path = f"{path}/{elem['label']}" if path else elem['label']
                # Also store the shortname for easier lookup
                shortname = elem.get('shortname', '')
                params[shortname] = {
                    'address': elem['address'],
                    'min': elem.get('min', 0),
                    'max': elem.get('max', 1),
                    'default': elem.get('init', 0),
                    'type': elem.get('type', '')
                }
                
                # Debug output to see parameter mappings
                if 'meta' in elem:
                    for meta in elem['meta']:
                        if 'osc' in meta:
                            print(f"OSC Parameter: {shortname} -> {elem['address']} (meta: {meta['osc']})")

    def send_osc(self, address, value):
        """Send an OSC message"""
        # Convert slashes in address to underscores to match shortname format
        short_addr = address.replace("/", "_")
        
        # Direct mapping for basic parameters
        direct_mappings = {
            "freq": f"/{self.synth_name}/freq",
            "gate": f"/{self.synth_name}/gate",
            "gain": f"/{self.synth_name}/gain",
        }
        
        if address in direct_mappings:
            full_address = direct_mappings[address]
        elif short_addr in self.osc_params:
            # Use the address from the loaded parameters
            full_address = self.osc_params[short_addr]['address']
        else:
            # Fallback to standard format
            full_address = f"/{self.synth_name}/{address}"
        
        self.osc_client.send_message(full_address, value)
        print(f"OSC: {full_address} = {value}")

    def handle_midi_message(self, message):
        """Process incoming MIDI messages and convert to OSC"""
        if message.type == 'note_on' and message.velocity > 0:
            # Convert MIDI note to frequency (A4 = 69 = 440Hz)
            freq = 440.0 * (2.0 ** ((message.note - 69) / 12.0))
            
            # Send frequency first, then gate
            self.send_osc("freq", freq)
            self.send_osc("gate", 1.0)
            
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
            
        elif message.type == 'polytouch':
            # Map polyphonic aftertouch to velocity
            norm_value = message.value / 127.0
            # Send as gain to affect volume
            self.send_osc("gain", norm_value)
            print(f"Poly Aftertouch: note={message.note}, value={message.value}")
            
        elif message.type == 'aftertouch':
            # Map channel aftertouch to filter cutoff by default
            norm_value = message.value / 127.0
            cutoff = 100 + (norm_value * 10000)  # Map to 100-10100 Hz
            self.send_osc("filter/cutoff", cutoff)
            print(f"Channel Aftertouch: value={message.value} -> cutoff={cutoff:.1f}Hz")
            
        elif message.type == 'control_change':
            # Map common CC numbers to synth parameters
            norm_value = message.value / 127.0
            
            # CC mapping - common MIDI CC numbers to synth parameters
            cc_mappings = {
                1: ("filter/env_amt", norm_value),                    # Mod wheel
                74: ("filter/cutoff", 100 + (norm_value * 10000)),    # Filter cutoff
                71: ("filter/resonance", norm_value * 0.9),           # Filter resonance
                73: ("amp/env/attack", 0.001 + (norm_value * 4.0)),   # Attack time
                72: ("amp/env/release", 0.001 + (norm_value * 8.0)),  # Release time
                75: ("amp/env/decay", 0.001 + (norm_value * 4.0)),    # Decay time
                31: ("osc1/level", norm_value),                       # Osc 1 level
                32: ("osc2/level", norm_value),                       # Osc 2 level
                33: ("osc3/level", norm_value),                       # Osc 3 level
                34: ("osc1/waveform", round(norm_value * 3)),         # Osc 1 waveform
                35: ("osc2/waveform", round(norm_value * 3)),         # Osc 2 waveform
                36: ("osc3/waveform", round(norm_value * 3)),         # Osc 3 waveform
                37: ("osc2/detune", -50 + (norm_value * 100)),        # Osc 2 detune
                38: ("osc3/detune", -50 + (norm_value * 100)),        # Osc 3 detune
                39: ("osc1/octave", -2 + round(norm_value * 4)),      # Osc 1 octave
                40: ("osc2/octave", -2 + round(norm_value * 4)),      # Osc 2 octave
                41: ("osc3/octave", -2 + round(norm_value * 4)),      # Osc 3 octave
            }
            
            if message.control in cc_mappings:
                param, value = cc_mappings[message.control]
                self.send_osc(param, value)
                print(f"CC{message.control}: {norm_value:.2f} -> {param}={value}")
            else:
                print(f"CC: control={message.control}, value={message.value}")

    def cleanup(self):
        """Ensure all notes are turned off"""
        print("Cleaning up...")
        self.send_osc("gate", 0.0)
        self.running = False
        print("Cleanup complete")

def prepare_faust_synth(synth_file):
    """Create JSON file for Faust synth parameter mapping"""
    base_name = synth_file.replace('.dsp', '')
    
    # Only create/update JSON if needed
    if not os.path.exists(f"{base_name}.dsp.json") or os.path.getmtime(synth_file) > os.path.getmtime(f"{base_name}.dsp.json"):
        print(f"Creating JSON description for: {synth_file}")
        try:
            # Create the JSON description for parameter mapping
            subprocess.run(['faust', '-json', '-o', f'{base_name}.dsp.json', synth_file], check=True)
            print(f"JSON creation successful: {base_name}.dsp.json")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error creating JSON file: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error during JSON creation: {e}")
            return False
    else:
        print(f"Synth JSON is up to date: {base_name}.dsp.json")
        return True

def launch_faust_synth(synth_path):
    """Launch the Faust synthesizer as a subprocess"""
    print(f"Launching Faust synth: {synth_path}")
    
    # Start synth as a subprocess
    try:
        process = subprocess.Popen(
            synth_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
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
    parser = argparse.ArgumentParser(description='Enhanced MIDI to OSC converter for Faust synths')
    parser.add_argument('--osc-ip', default='127.0.0.1', help='OSC server IP address')
    parser.add_argument('--osc-port', type=int, default=5510, help='OSC server port')
    parser.add_argument('--synth-name', default='minimono', 
                      help='Faust synth name (without extension)')
    parser.add_argument('--no-json', action='store_true',
                      help='Do not generate JSON parameter file')
    parser.add_argument('--no-launch', action='store_true',
                      help='Do not launch the Faust synth (assume it is already running)')
    args = parser.parse_args()
    
    # Build paths
    synth_path = f'./{args.synth_name}'
    synth_file = f'{args.synth_name}.dsp'
    
    # Check if binary exists
    if not os.path.exists(synth_path):
        print(f"Error: Synth binary not found at {synth_path}")
        print("Please precompile the Faust synth with: faust2jackconsole <synth_name>.dsp")
        return
    
    # Create JSON parameter file if needed
    if not args.no_json:
        if not prepare_faust_synth(synth_file):
            print("Failed to create JSON parameter file. Continuing anyway...")
    
    # Launch Faust synth if requested
    synth_process = None
    if not args.no_launch:
        # Launch with OSC control enabled
        synth_process = launch_faust_synth(f"{synth_path} --control 1")
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
                            print(f"Successfully connected to MIDI port: {selection}")
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
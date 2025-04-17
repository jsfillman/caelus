import mido
import argparse
import threading
import time
import subprocess
import os
import signal
import sys
from pythonosc import udp_client

class MidiToOSC:
    def __init__(self, osc_ip="127.0.0.1", osc_port=5510, program_name="simple_saw"):
        # OSC client setup
        self.osc_client = udp_client.SimpleUDPClient(osc_ip, osc_port)
        self.program_name = program_name
        self.running = True
        self.active_notes = set()  # Keep track of active notes for cleanup

    def send_osc(self, address, value):
        """Send an OSC message with the program name prefix"""
        full_address = f"/{self.program_name}/{address}"
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
            # Could map polyphonic aftertouch to some parameter
            print(f"Poly Aftertouch: note={message.note}, value={message.value}")
            
        elif message.type == 'aftertouch':
            # Could map channel aftertouch to some parameter
            print(f"Channel Aftertouch: value={message.value}")
            
        elif message.type == 'control_change':
            # Could map CCs to additional parameters if needed
            print(f"CC: control={message.control}, value={message.value}")

    def cleanup(self):
        """Ensure all notes are turned off"""
        print("Cleaning up...")
        self.send_osc("gate", 0.0)
        self.running = False
        print("Cleanup complete")

def launch_faust_synth(synth_path="./simple_saw"):
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
    parser = argparse.ArgumentParser(description='MIDI to OSC converter for Faust synths')
    parser.add_argument('--osc-ip', default='127.0.0.1', help='OSC server IP address')
    parser.add_argument('--osc-port', type=int, default=5510, help='OSC server port')
    parser.add_argument('--program-name', default='simple_saw', 
                      help='Faust program name (prefix for OSC messages)')
    parser.add_argument('--synth-path', default='./simple_saw',
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
    
    # Get MIDI port selection directly with no buffering issues
    selection = None
    while selection is None:
        try:
            port_input = input("Select MIDI input port number (or 'q' to quit): ")
            if port_input.lower() in ('q', 'quit', 'exit'):
                print("Exiting...")
                if synth_process:
                    synth_process.terminate()
                return
                
            idx = int(port_input)
            if 0 <= idx < len(midi_inputs):
                selection = midi_inputs[idx]
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
    converter = MidiToOSC(args.osc_ip, args.osc_port, args.program_name)
    
    print(f"Using MIDI port: {selection}")
    print(f"Sending OSC to: {args.osc_ip}:{args.osc_port}")
    print(f"Using program name prefix: /{args.program_name}/")
    print("Ready for MIDI input. Type 'q' and press Enter to quit, or press Ctrl+C.")
    
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
    
    # Main loop to check for exit command
    try:
        while converter.running:
            try:
                cmd = input("")  # Wait for any input
                if cmd.lower() in ('q', 'quit', 'exit'):
                    print("Exit command received. Cleaning up...")
                    break
            except EOFError:
                # Handle Ctrl+D
                print("\nInput terminated. Exiting...")
                break
    except KeyboardInterrupt:
        print("\nExiting...")
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
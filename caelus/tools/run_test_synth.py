#!/usr/bin/env python3
"""
Test Synth

This script creates a simple OSC server that acts like a synthesizer.
It listens on a specified port and prints any OSC messages it receives.
Use this to test if the OSC bridge is sending messages to the synth.

Usage:
1. Shut down any existing synth process
2. Run this script with the same port as specified in voices.yaml
3. Start Caelus and play MIDI notes
4. This script will show any OSC messages that would be sent to the real synth
"""

import argparse
import sys
import time
import signal
from datetime import datetime
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer

class TestSynth:
    """Fake synth that listens for OSC messages"""
    
    def __init__(self, port=5510, synth_name="simple"):
        """Initialize with port to listen on"""
        self.port = port
        self.synth_name = synth_name
        self.server = None
        self.running = False
        self.message_count = 0
        self.gate_count = 0
        self.freq_count = 0
        self.gain_count = 0
        
    def handle_any_message(self, address, *args):
        """Handler for any OSC message"""
        # Format arguments for display
        if len(args) == 0:
            args_formatted = "(no args)"
        elif len(args) == 1:
            args_formatted = str(args[0])
        else:
            args_formatted = str(args)
            
        # Get timestamp
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        
        # Increment counters
        self.message_count += 1
        
        # Track specific messages
        if '/gate' in address:
            self.gate_count += 1
            
            # If gate on, print in green and play a "note"
            if args and args[0] > 0:
                print(f"\033[32m[{timestamp}] GATE ON: {address} = {args_formatted}\033[0m")
                # Print a visual "note"
                print(" ♪ ", end='', flush=True)
            else:
                print(f"[{timestamp}] GATE OFF: {address} = {args_formatted}")
        elif '/freq' in address:
            self.freq_count += 1
            print(f"[{timestamp}] FREQ: {address} = {args_formatted}")
        elif '/gain' in address:
            self.gain_count += 1
            print(f"[{timestamp}] GAIN: {address} = {args_formatted}")
        else:
            # Print other messages
            print(f"[{timestamp}] {address} = {args_formatted}")
        
    def start(self):
        """Start the test synth"""
        try:
            # Create a dispatcher for all OSC messages
            dispatcher = Dispatcher()
            
            # Register handlers
            dispatcher.set_default_handler(self.handle_any_message)
            
            # Create server
            addr = ('0.0.0.0', self.port)
            self.server = ThreadingOSCUDPServer(addr, dispatcher)
            self.running = True
            
            print(f"=== Test Synth running on port {self.port} ===")
            print(f"Expected synth name: {self.synth_name}")
            print(f"Pretending to be a synth on port {self.port}")
            print("This will show any OSC messages that would be sent to the real synth")
            print("Press Ctrl+C to stop")
            print("=" * 50)
            
            # Start server
            self.server.serve_forever()
            
        except KeyboardInterrupt:
            print("\nStopping...")
        except Exception as e:
            print(f"Error starting test synth: {e}")
            if "Address already in use" in str(e):
                print(f"\nPort {self.port} is already in use.")
                print("Make sure to stop any existing synth process first.")
                print("You can check with: lsof -i :{self.port}")
            return False
            
        return True
    
    def stop(self):
        """Stop the test synth"""
        self.running = False
        
        if self.server:
            self.server.shutdown()
        
        # Print summary
        print("\n=== Test Synth Summary ===")
        print(f"Total OSC messages received: {self.message_count}")
        print(f"gate messages: {self.gate_count}")
        print(f"freq messages: {self.freq_count}")
        print(f"gain messages: {self.gain_count}")
        
        if self.message_count == 0:
            print("\nNo OSC messages were received!")
            print("This means the OSC bridge is not sending messages to the synth.")
            print("Possible issues:")
            print("1. No MIDI input is happening")
            print("2. MIDI-OSC bridge is not converting MIDI to OSC")
            print("3. OSC router is not forwarding messages to the synth")
            print("4. OSC router is sending to a different port than expected")
        else:
            if self.gate_count == 0:
                print("\nNo gate messages were received!")
                print("This means notes aren't being played.")
            elif self.freq_count == 0:
                print("\nNo freq messages were received!")
                print("This means pitch information isn't being sent.")
            elif self.gain_count == 0:
                print("\nNo gain messages were received!")
                print("This means velocity information isn't being sent.")
                
            if self.gate_count > 0 and self.freq_count > 0 and self.gain_count > 0:
                print("\nAll necessary messages for playing notes were received.")
                print("Check if you're using the correct synth_name in voices.yaml.")
                print(f"This test expected '{self.synth_name}', but the router might be using a different name.")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Run a test synth that listens for OSC")
    parser.add_argument("-p", "--port", type=int, default=5510,
                       help="Port to listen on (default: 5510)")
    parser.add_argument("-n", "--name", type=str, default="simple",
                       help="Synth name to expect in OSC paths (default: simple)")
    
    args = parser.parse_args()
    
    # Create test synth
    synth = TestSynth(args.port, args.name)
    
    # Set up signal handler for clean exit
    def signal_handler(sig, frame):
        print("\nStopping test synth...")
        synth.stop()
        sys.exit(0)
        
    signal.signal(signal.SIGINT, signal_handler)
    
    # Start test synth
    try:
        synth.start()
    except KeyboardInterrupt:
        synth.stop()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
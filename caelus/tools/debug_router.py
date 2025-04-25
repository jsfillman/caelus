#!/usr/bin/env python3
"""
Debug tool for monitoring the OSC router.
This script:
1. Connects directly to the router port
2. Sends MIDI-like OSC messages (note_on, note_off, etc.)
3. Traces the resulting OSC messages sent to the synth
"""

import os
import sys
import time
import argparse
from pythonosc import udp_client, osc_server, dispatcher
from threading import Thread

# Add parent directory to path so we can import modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from lib.core.utils import LOG

class OSCDebugger:
    """OSC debugging tool"""
    
    def __init__(self, router_port=9000, synth_port=5510, 
                 router_host="127.0.0.1", synth_host="127.0.0.1"):
        """Initialize the OSC debugger"""
        self.router_port = router_port
        self.synth_port = synth_port
        self.router_host = router_host
        self.synth_host = synth_host
        
        # Create OSC client for sending messages to router
        self.router_client = udp_client.SimpleUDPClient(router_host, router_port)
        LOG.info(f"Created router client connecting to {router_host}:{router_port}")
        
        # Create dispatcher for receiving OSC messages
        self.dispatcher = dispatcher.Dispatcher()
        self.dispatcher.map("/*", self.handle_any_message)
        
        # Configure listening server
        self.server = None
        self.server_thread = None
        self.running = False
    
    def start_listening(self, port=9001):
        """Start listening for OSC messages"""
        from pythonosc.osc_server import ThreadingOSCUDPServer
        
        try:
            # Create server
            self.server = ThreadingOSCUDPServer(("0.0.0.0", port), self.dispatcher)
            LOG.info(f"Starting OSC listener on port {port}")
            
            # Start server in background thread
            self.running = True
            self.server_thread = Thread(target=self._run_server)
            self.server_thread.daemon = True
            self.server_thread.start()
            
            return True
        except Exception as e:
            LOG.error(f"Error starting OSC listener: {e}")
            return False
    
    def _run_server(self):
        """Run the OSC server in a background thread"""
        try:
            while self.running:
                self.server.handle_request()
        except Exception as e:
            LOG.error(f"Error in OSC listener: {e}")
    
    def stop_listening(self):
        """Stop listening for OSC messages"""
        self.running = False
        if self.server:
            try:
                self.server.server_close()
            except Exception as e:
                LOG.error(f"Error closing server: {e}")
        LOG.info("OSC listener stopped")
    
    def handle_any_message(self, address, *args):
        """Handle any OSC message"""
        # Format the message
        args_str = ', '.join(str(arg) for arg in args)
        LOG.info(f"Received OSC: {address} [{args_str}]")
    
    def test_note_sequence(self):
        """Test sending a sequence of notes"""
        LOG.info("\n--- Testing note sequence ---")
        
        # Middle C major scale
        notes = [60, 62, 64, 65, 67, 69, 71, 72]
        
        for note in notes:
            # Note on
            LOG.info(f"Sending note_on for note {note}")
            self.router_client.send_message("/router/note_on", [note, 0.8])
            time.sleep(0.3)
            
            # Note off
            LOG.info(f"Sending note_off for note {note}")
            self.router_client.send_message("/router/note_off", [note])
            time.sleep(0.1)
    
    def test_chord(self):
        """Test sending a chord (multiple notes at once)"""
        LOG.info("\n--- Testing chord ---")
        
        # C major chord (C-E-G)
        LOG.info("Sending C major chord")
        self.router_client.send_message("/router/note_on", [60, 0.8])  # C
        time.sleep(0.1)
        self.router_client.send_message("/router/note_on", [64, 0.8])  # E
        time.sleep(0.1)
        self.router_client.send_message("/router/note_on", [67, 0.8])  # G
        time.sleep(1.0)
        
        # Note off
        LOG.info("Sending note_off for chord")
        self.router_client.send_message("/router/note_off", [60])
        time.sleep(0.1)
        self.router_client.send_message("/router/note_off", [64])
        time.sleep(0.1)
        self.router_client.send_message("/router/note_off", [67])
    
    def test_control_changes(self):
        """Test sending control change messages"""
        LOG.info("\n--- Testing control changes ---")
        
        # Modulation wheel (CC 1)
        LOG.info("Sending modulation wheel (CC 1)")
        for value in [0, 32, 64, 96, 127]:
            normalized = value / 127.0
            LOG.info(f"  Setting mod wheel to {value} ({normalized:.2f})")
            self.router_client.send_message("/router/cc", [1, value])
            time.sleep(0.3)
        
        # Reset to 0
        LOG.info("  Resetting mod wheel to 0")
        self.router_client.send_message("/router/cc", [1, 0])
        
        # Sustain pedal (CC 64)
        LOG.info("Testing sustain pedal (CC 64)")
        LOG.info("  Setting sustain ON")
        self.router_client.send_message("/router/cc", [64, 127])
        time.sleep(0.5)
        LOG.info("  Setting sustain OFF")
        self.router_client.send_message("/router/cc", [64, 0])
    
    def test_patch_parameters(self):
        """Test sending patch parameters"""
        LOG.info("\n--- Testing patch parameters ---")
        
        # Cutoff
        LOG.info("Sending cutoff changes")
        for cutoff in [500, 1000, 2000, 5000, 1000]:
            LOG.info(f"  Setting cutoff to {cutoff}")
            self.router_client.send_message("/router/param_all", ["cutoff", cutoff])
            time.sleep(0.5)
    
    def test_all(self):
        """Run all tests"""
        try:
            # Test note sequence
            self.test_note_sequence()
            time.sleep(1.0)
            
            # Test chord
            self.test_chord()
            time.sleep(1.0)
            
            # Test CC messages
            self.test_control_changes()
            time.sleep(1.0)
            
            # Test patch parameters
            self.test_patch_parameters()
            time.sleep(1.0)
            
            # Send all notes off
            LOG.info("\nSending all_notes_off")
            self.router_client.send_message("/router/all_notes_off", [])
            
            LOG.info("\nTests completed. Check for sound output.")
            
        except Exception as e:
            LOG.error(f"Error in tests: {e}")
            import traceback
            traceback.print_exc()

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Debug OSC router communication")
    parser.add_argument("--router-port", type=int, default=9000, help="Router OSC port")
    parser.add_argument("--synth-port", type=int, default=5510, help="Synth OSC port")
    parser.add_argument("--listen-port", type=int, default=9001, help="Port to listen on for OSC messages")
    parser.add_argument("--listen", action="store_true", help="Listen for OSC messages")
    
    args = parser.parse_args()
    
    # Create debugger
    debugger = OSCDebugger(
        router_port=args.router_port,
        synth_port=args.synth_port
    )
    
    # Start listening if requested
    if args.listen:
        LOG.info(f"Starting OSC listener on port {args.listen_port}")
        if not debugger.start_listening(args.listen_port):
            return 1
    
    # Run tests
    try:
        debugger.test_all()
        
        # Keep running if listening
        if args.listen:
            LOG.info("OSC listener active. Press Ctrl+C to stop.")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                LOG.info("Stopping...")
        
    except KeyboardInterrupt:
        LOG.info("Stopping...")
    finally:
        if args.listen:
            debugger.stop_listening()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
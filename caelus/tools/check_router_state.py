#!/usr/bin/env python3
"""
Check OSC Router State

This script sends OSC messages to the router to query its current state,
including active voices, configuration, and whether it's properly initialized.
"""

import argparse
import sys
import time
from pythonosc import udp_client, dispatcher, osc_server
import threading
import signal

class RouterStateChecker:
    """Check the state of the OSC Router"""
    
    def __init__(self, router_port=9000, listen_port=9876):
        """Initialize with ports"""
        self.router_port = router_port
        self.listen_port = listen_port
        self.router_client = None
        self.server = None
        self.server_thread = None
        self.running = False
        self.response_received = False
        
    def start_listener(self):
        """Start an OSC server to receive responses"""
        try:
            # Create dispatcher for OSC messages
            disp = dispatcher.Dispatcher()
            disp.set_default_handler(self.handle_any_message)
            
            # Set up specific handlers
            disp.map("/router/value/*", self.handle_value_response)
            
            # Create server
            self.server = osc_server.ThreadingOSCUDPServer(
                ("0.0.0.0", self.listen_port), disp)
            
            # Start server in a thread
            self.running = True
            self.server_thread = threading.Thread(target=self._server_thread)
            self.server_thread.daemon = True
            self.server_thread.start()
            
            print(f"Listening for OSC responses on port {self.listen_port}")
            return True
            
        except Exception as e:
            print(f"Error starting listener: {e}")
            return False
    
    def _server_thread(self):
        """Thread function for server"""
        try:
            while self.running:
                self.server.handle_request()
        except Exception as e:
            if self.running:
                print(f"Error in server thread: {e}")
    
    def handle_any_message(self, address, *args):
        """Handler for any OSC message"""
        print(f"Received OSC message: {address} {args}")
        self.response_received = True
    
    def handle_value_response(self, address, *args):
        """Handler for router value responses"""
        var_path = address.split('/')[-1]
        print(f"Router variable {var_path} = {args[0] if args else 'None'}")
        self.response_received = True
    
    def connect_to_router(self):
        """Connect to the OSC router"""
        try:
            self.router_client = udp_client.SimpleUDPClient("127.0.0.1", self.router_port)
            print(f"Connected to router at 127.0.0.1:{self.router_port}")
            return True
        except Exception as e:
            print(f"Error connecting to router: {e}")
            return False
    
    def check_router_alive(self):
        """Check if the router is responsive"""
        print("\n=== Testing Router Connectivity ===")
        self.response_received = False
        try:
            # Register our listener with the router
            print(f"Registering listener at 127.0.0.1:{self.listen_port}")
            self.router_client.send_message("/router/register_ui", ["127.0.0.1", self.listen_port])
            
            # Wait for a response
            time.sleep(1)
            
            if self.response_received:
                print("✅ Router responded to registration - it's alive!")
                return True
            else:
                print("❌ No response from router to registration")
                
                # Try a direct status request
                print("Trying direct status request...")
                self.router_client.send_message("/router/get/status", ["status"])
                
                # Wait for a response
                time.sleep(1)
                
                if self.response_received:
                    print("✅ Router responded to status request - it's alive!")
                    return True
                else:
                    print("❌ No response from router to status request")
                    return False
                
        except Exception as e:
            print(f"Error checking router alive: {e}")
            return False
    
    def check_voice_configuration(self):
        """Check voice configuration in the router"""
        print("\n=== Checking Voice Configuration ===")
        self.response_received = False
        
        try:
            # Try to get synth_name
            print("Requesting synth_name...")
            self.router_client.send_message("/router/get/synth_name", ["synth_name"])
            time.sleep(0.5)
            
            # Try to get voice count
            print("Requesting voice count...")
            self.router_client.send_message("/router/get/voice_count", ["voice_count"])
            time.sleep(0.5)
            
            # Try to get voice details
            print("Requesting active voices...")
            self.router_client.send_message("/router/get/active_voices", ["active_voices"])
            time.sleep(0.5)
            
            if not self.response_received:
                print("❌ No response to voice configuration queries")
                print("The router appears to be running but not properly configured")
            
        except Exception as e:
            print(f"Error checking voice configuration: {e}")
    
    def send_test_note(self):
        """Send a test note to the router"""
        print("\n=== Sending Test Note to Router ===")
        
        try:
            # Send a test note on
            print("Sending note_on for middle C (60)...")
            self.router_client.send_message("/router/note_on", [60, 0.8])
            time.sleep(1)
            
            # Send note off
            print("Sending note_off for middle C (60)...")
            self.router_client.send_message("/router/note_off", [60])
            
            print("Test note sent. Check if you heard anything.")
            
        except Exception as e:
            print(f"Error sending test note: {e}")
    
    def check_router_variables(self):
        """Check various router variables"""
        print("\n=== Checking Router Variables ===")
        
        variables = [
            "synth_name",
            "synth_host",
            "router_port",
            "voice_count",
            "active_voices",
            "note_count"
        ]
        
        for var in variables:
            print(f"Requesting {var}...")
            self.router_client.send_message("/router/get/" + var, [var])
            time.sleep(0.5)
    
    def stop(self):
        """Stop the checker"""
        self.running = False
        
        if self.server:
            self.server.shutdown()

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Check OSC Router State")
    parser.add_argument("-r", "--router-port", type=int, default=9000,
                      help="Router port (default: 9000)")
    parser.add_argument("-l", "--listen-port", type=int, default=9876,
                      help="Port to listen for responses (default: 9876)")
    
    args = parser.parse_args()
    
    # Create checker
    checker = RouterStateChecker(args.router_port, args.listen_port)
    
    # Set up signal handler for clean exit
    def signal_handler(sig, frame):
        print("\nStopping...")
        checker.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Start listener
        if not checker.start_listener():
            return 1
        
        # Connect to router
        if not checker.connect_to_router():
            print("Failed to connect to router.")
            return 1
        
        # Run checks
        router_alive = checker.check_router_alive()
        
        if router_alive:
            # Run additional checks
            checker.check_voice_configuration()
            checker.check_router_variables()
            checker.send_test_note()
            
            print("\n=== Router Diagnostics Complete ===")
            print("Try running tools/inject_midi.py while listening with tools/osc_monitor.py")
            print("If you hear sound with direct tests but not through the router,")
            print("the issue is in the router's voice allocation logic.")
        else:
            print("\n❌ Router is not responding. Check if it's running.")
            print("Try running Caelus and check the console for router errors.")
        
        # Keep running until Ctrl+C to receive any delayed responses
        print("\nPress Ctrl+C to exit...")
        while True:
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        checker.stop()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
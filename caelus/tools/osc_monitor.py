#!/usr/bin/env python3
"""
OSC Traffic Monitor

This script listens for and logs all OSC messages on specified ports.
Great for debugging OSC communication between applications.
"""

import argparse
import sys
import time
import threading
from datetime import datetime
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer

class OSCMonitor:
    """Monitor OSC traffic on specified ports"""
    
    def __init__(self, ports, verbose=False):
        """Initialize with ports to monitor"""
        self.ports = ports
        self.verbose = verbose
        self.servers = []
        self.threads = []
        self.running = False
        
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
        
        # Get port from server attribute
        port = getattr(self._current_server, '_port', '?')
            
        # Print the message details
        print(f"[{timestamp}] Port {port} | {address} = {args_formatted}")
        
        # Print detailed info if verbose
        if self.verbose:
            print(f"  Type(s): {', '.join(type(arg).__name__ for arg in args)}")
            if hasattr(self._current_server, '_client_address'):
                addr = self._current_server._client_address
                print(f"  From: {addr[0]}:{addr[1]}")
            
    def start_monitoring(self):
        """Start monitoring all ports"""
        self.running = True
        
        for port in self.ports:
            try:
                # Create a dispatcher for this port
                dispatcher = Dispatcher()
                dispatcher.set_default_handler(self.handle_any_message)
                
                # Create server
                server = ThreadingOSCUDPServer(('0.0.0.0', port), dispatcher)
                server._port = port  # Add custom attribute for handler
                self.servers.append(server)
                
                # Create and start thread
                thread = threading.Thread(
                    target=self._server_thread, 
                    args=(server, port),
                    daemon=True
                )
                self.threads.append(thread)
                thread.start()
                
                print(f"Monitoring OSC on port {port}...")
                
            except Exception as e:
                print(f"Error starting server on port {port}: {e}")
        
        # Print status
        if self.servers:
            ports_str = ", ".join(str(p) for p in self.ports if p in [s._port for s in self.servers])
            print(f"Monitoring OSC traffic on port(s): {ports_str}")
            print("Press Ctrl+C to stop.")
        else:
            print("No servers started. Exiting.")
            return False
            
        return True
    
    def _server_thread(self, server, port):
        """Thread function for each server"""
        try:
            self._current_server = server
            
            # Custom serve_forever that can be stopped
            while self.running:
                server.handle_request()
                
        except Exception as e:
            if self.running:  # Only show error if not shutting down
                print(f"Error in server thread for port {port}: {e}")
    
    def stop_monitoring(self):
        """Stop all monitoring"""
        self.running = False
        
        # Close all servers
        for server in self.servers:
            try:
                server.server_close()
            except:
                pass
                
        print("Stopped monitoring.")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Monitor OSC traffic on specified ports")
    parser.add_argument("ports", type=int, nargs="+", 
                      help="OSC ports to monitor (e.g. 5510 9000 9001)")
    parser.add_argument("-v", "--verbose", action="store_true",
                      help="Show verbose information about each message")
    
    args = parser.parse_args()
    
    # Create monitor
    monitor = OSCMonitor(args.ports, args.verbose)
    
    try:
        # Start monitoring
        if not monitor.start_monitoring():
            return 1
            
        # Keep running until Ctrl+C
        while True:
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        monitor.stop_monitoring()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
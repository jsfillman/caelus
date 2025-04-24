#!/usr/bin/env python3
"""
OSC Monitor Tool - Listen for OSC messages on specified ports.

This script sets up OSC servers to capture and display incoming messages,
useful for debugging OSC communication issues.
"""
import argparse
import sys
import os
import logging
import threading
import time
from typing import List, Dict, Any

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
LOG = logging.getLogger(__name__)

# Import OSC libraries after path is set
from pythonosc import dispatcher
from pythonosc import osc_server

class OSCMonitor:
    """Class to monitor OSC messages on multiple ports simultaneously."""
    
    def __init__(self, ports: List[int]):
        """
        Initialize OSC monitors on multiple ports.
        
        Args:
            ports: List of ports to monitor
        """
        self.ports = ports
        self.servers = {}
        self.running = True
        self.message_counts: Dict[int, int] = {port: 0 for port in ports}
        self.last_message_time: Dict[int, float] = {port: 0 for port in ports}
    
    def _default_handler(self, address: str, port: int, *args: Any) -> None:
        """Default handler for all OSC messages."""
        now = time.time()
        self.message_counts[port] += 1
        self.last_message_time[port] = now
        
        # Format the args based on their types
        formatted_args = []
        for arg in args:
            if isinstance(arg, float):
                formatted_args.append(f"{arg:.6f}")
            else:
                formatted_args.append(str(arg))
        
        args_str = ", ".join(formatted_args)
        LOG.info(f"OSC [{port}] {address} {args_str}")
    
    def _create_server(self, port: int) -> None:
        """
        Create and start an OSC server on the specified port.
        
        Args:
            port: Port to listen on
        """
        try:
            # Create dispatcher with wildcard handler
            disp = dispatcher.Dispatcher()
            
            # Create handler specific to this port
            def handler(address, *args):
                return self._default_handler(address, port, *args)
            
            # Register wildcard handler
            disp.map("/*", handler)
            
            # Create server
            server = osc_server.ThreadingOSCUDPServer(("0.0.0.0", port), disp)
            LOG.info(f"Listening for OSC messages on port {port}")
            
            # Store server
            self.servers[port] = server
            
            # Start server in thread
            thread = threading.Thread(target=self._run_server, args=(port,))
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            LOG.error(f"Error creating OSC server on port {port}: {e}")
    
    def _run_server(self, port: int) -> None:
        """Run the server for the specified port."""
        server = self.servers.get(port)
        if not server:
            return
            
        try:
            # Custom serve forever that can be stopped
            while self.running:
                server.handle_request()
                
        except Exception as e:
            LOG.error(f"Error in OSC server on port {port}: {e}")
    
    def start(self) -> None:
        """Start all OSC monitors."""
        for port in self.ports:
            self._create_server(port)
    
    def print_stats(self) -> None:
        """Print message statistics."""
        LOG.info("=== OSC Monitor Statistics ===")
        for port in sorted(self.ports):
            count = self.message_counts[port]
            last_time = self.last_message_time[port]
            
            if count > 0:
                ago = time.time() - last_time
                LOG.info(f"Port {port}: {count} messages, last message {ago:.1f} seconds ago")
            else:
                LOG.info(f"Port {port}: No messages received")
        LOG.info("=============================")
    
    def stop(self) -> None:
        """Stop all OSC monitors."""
        self.running = False
        
        # Close all server sockets
        for port, server in self.servers.items():
            try:
                LOG.info(f"Closing OSC server on port {port}")
                server.server_close()
            except Exception as e:
                LOG.error(f"Error closing server on port {port}: {e}")

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="OSC Monitor Tool")
    parser.add_argument(
        "--ports", 
        type=str, 
        default="9000,5510,5610,5710,5810",
        help="Comma-separated list of ports to monitor (default: 9000,5510,5610,5710,5810)"
    )
    return parser.parse_args()

def main() -> int:
    """Main entry point."""
    args = parse_args()
    
    # Parse ports
    try:
        ports = [int(p.strip()) for p in args.ports.split(",")]
    except ValueError:
        LOG.error(f"Invalid port format: {args.ports}")
        return 1
    
    # Create and start monitor
    monitor = OSCMonitor(ports)
    monitor.start()
    
    try:
        LOG.info("OSC Monitor running. Press Ctrl+C to stop.")
        
        # Print stats periodically
        while True:
            time.sleep(10)
            monitor.print_stats()
            
    except KeyboardInterrupt:
        LOG.info("OSC Monitor stopped by user")
    
    # Clean up
    monitor.stop()
    return 0

if __name__ == "__main__":
    sys.exit(main()) 
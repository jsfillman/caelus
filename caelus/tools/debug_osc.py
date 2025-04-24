#!/usr/bin/env python3
"""
OSC Debug Tool - Test connectivity between OSC router and synth instances.

This script sends test OSC messages to verify if synth instances are reachable
and if messages are properly formatted.
"""
import argparse
import time
import sys
import os
import logging
from typing import List, Optional

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
LOG = logging.getLogger(__name__)

# Import OSC libraries after path is set
from pythonosc import udp_client

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="OSC Debug Tool")
    parser.add_argument(
        "--host", 
        type=str, 
        default="127.0.0.1",
        help="Target host IP (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--ports", 
        type=str, 
        default="5510,5610,5710,5810",
        help="Comma-separated list of ports to test (default: 5510,5610,5710,5810)"
    )
    parser.add_argument(
        "--synth-name", 
        type=str, 
        default="synth",
        help="Synth name to include in OSC path (default: synth)"
    )
    parser.add_argument(
        "--test-note", 
        action="store_true",
        help="Send test note on/off sequence"
    )
    return parser.parse_args()

def test_connectivity(host: str, ports: List[int], synth_name: str) -> List[int]:
    """
    Test basic connectivity to each port.
    
    Args:
        host: Target host IP
        ports: List of ports to test
        synth_name: Synth name to include in OSC path
        
    Returns:
        List of ports that responded successfully
    """
    LOG.info(f"Testing connectivity to {host} on ports {ports}")
    
    successful_ports = []
    
    for port in ports:
        try:
            # Create client
            client = udp_client.SimpleUDPClient(host, port)
            LOG.info(f"Testing port {port}...")
            
            # Send simple test message
            path = f"/{synth_name}/ping"
            value = 1.0
            LOG.debug(f"Sending {path} = {value} to {host}:{port}")
            
            # Send the message
            client.send_message(path, value)
            
            # We can't know if it was received, so assume success if no exception
            LOG.info(f"Message sent to {host}:{port} without errors")
            successful_ports.append(port)
            
        except Exception as e:
            LOG.error(f"Error connecting to {host}:{port}: {e}")
    
    return successful_ports

def send_test_note(host: str, ports: List[int], synth_name: str) -> None:
    """
    Send a test note sequence to verify note on/off functionality.
    
    Args:
        host: Target host IP
        ports: List of ports to test
        synth_name: Synth name to include in OSC path
    """
    LOG.info(f"Sending test notes to {host} on ports {ports}")
    
    for port in ports:
        try:
            # Create client
            client = udp_client.SimpleUDPClient(host, port)
            LOG.info(f"Testing note on port {port}...")
            
            # Get MIDI note to frequency conversion function
            from lib.common.utils import midi_to_freq
            
            # Send note on (middle C)
            note = 60  # Middle C
            freq = midi_to_freq(note)
            
            # Send frequency
            client.send_message(f"/{synth_name}/freq", freq)
            LOG.info(f"Sent freq {freq} Hz to {host}:{port}")
            
            # Send gate on
            client.send_message(f"/{synth_name}/gate", 1.0)
            LOG.info(f"Sent gate ON to {host}:{port}")
            
            # Send gain
            client.send_message(f"/{synth_name}/gain", 0.5)
            LOG.info(f"Sent gain 0.5 to {host}:{port}")
            
            # Wait for a second
            LOG.info("Waiting 1 second...")
            time.sleep(1.0)
            
            # Send gate off
            client.send_message(f"/{synth_name}/gate", 0.0)
            LOG.info(f"Sent gate OFF to {host}:{port}")
            
            # Wait briefly before testing next port
            time.sleep(0.5)
            
        except Exception as e:
            LOG.error(f"Error sending test note to {host}:{port}: {e}")

def main() -> int:
    """Main entry point."""
    args = parse_args()
    
    # Parse ports
    try:
        ports = [int(p.strip()) for p in args.ports.split(",")]
    except ValueError:
        LOG.error(f"Invalid port format: {args.ports}")
        return 1
    
    # Test connectivity
    successful_ports = test_connectivity(args.host, ports, args.synth_name)
    
    if not successful_ports:
        LOG.error("No ports responded successfully")
        return 1
        
    LOG.info(f"Successfully connected to ports: {successful_ports}")
    
    # Test note if requested
    if args.test_note:
        send_test_note(args.host, successful_ports, args.synth_name)
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 
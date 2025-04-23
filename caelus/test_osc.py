#!/usr/bin/env python3
"""
Simple OSC test script to verify communication with the router
"""
import sys
import time
from pythonosc import udp_client

# Configuration
OSC_IP = "127.0.0.1"
OSC_PORT = 9001
ROUTER_NAME = "router"

def main():
    # Create OSC client
    print(f"Creating OSC client to {OSC_IP}:{OSC_PORT}")
    osc = udp_client.SimpleUDPClient(OSC_IP, OSC_PORT)
    
    # Send a test note
    print("Sending test note_on message...")
    osc.send_message(f"/{ROUTER_NAME}/note_on", [60, 0.8])  # Middle C, velocity 0.8
    print("Sent note_on")
    
    # Wait
    time.sleep(1)
    
    # Send note off
    print("Sending test note_off message...")
    osc.send_message(f"/{ROUTER_NAME}/note_off", [60])
    print("Sent note_off")
    
    # Send some CC messages
    print("Sending test CC message (modulation wheel)...")
    osc.send_message(f"/{ROUTER_NAME}/cc", [1, 0.5])  # CC 1 (mod wheel), value 0.5
    print("Sent CC")
    
    # Test direct parameter control
    print("Sending test direct parameter control...")
    osc.send_message(f"/{ROUTER_NAME}/param_all/cutoff", ["cutoff", 2000])
    print("Sent parameter control")
    
    print("All test messages sent. Check the router logs to see if they were received.")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 
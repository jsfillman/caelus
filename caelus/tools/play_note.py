#!/usr/bin/env python3
"""
Simple script to play a note on the synth directly via OSC.
Sends note on, waits for specified duration, then sends note off.
"""

import argparse
import time
import sys
from pythonosc import udp_client

def main():
    """Play a note via OSC"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Play a note via OSC")
    parser.add_argument("-p", "--port", type=int, default=5510, 
                        help="Synth OSC port (default: 5510)")
    parser.add_argument("-H", "--host", type=str, default="127.0.0.1",
                        help="Synth host (default: 127.0.0.1)")
    parser.add_argument("-n", "--note", type=int, default=60,
                        help="MIDI note number (0-127, default: 60/middle C)")
    parser.add_argument("-v", "--velocity", type=float, default=0.8,
                        help="Note velocity (0.0-1.0, default: 0.8)")
    parser.add_argument("-d", "--duration", type=float, default=3.0,
                        help="Note duration in seconds (default: 3.0)")
    parser.add_argument("-s", "--synth-name", type=str, default="simple",
                        help="Synth name for OSC path (default: simple)")
    parser.add_argument("-f", "--freq", type=float, default=None,
                        help="Frequency in Hz (overrides note number)")
    
    args = parser.parse_args()
    
    # Create OSC client
    client = udp_client.SimpleUDPClient(args.host, args.port)
    print(f"Connected to OSC at {args.host}:{args.port}")
    
    # Calculate frequency from MIDI note number
    if args.freq is None:
        freq = 440.0 * (2 ** ((args.note - 69) / 12))
    else:
        freq = args.freq
    
    # Format OSC path - match the format that works
    path_prefix = f"/{args.synth_name}"
    
    # Send note on
    print(f"Playing note: MIDI {args.note} ({freq:.2f} Hz) for {args.duration} seconds")
    print(f"Sending {path_prefix}/freq = {freq}")
    client.send_message(f"{path_prefix}/freq", freq)
    print(f"Sending {path_prefix}/gain = {args.velocity}")
    client.send_message(f"{path_prefix}/gain", args.velocity)
    print(f"Sending {path_prefix}/gate = 1")
    client.send_message(f"{path_prefix}/gate", 1)
    
    # Wait for duration
    time.sleep(args.duration)
    
    # Send note off
    print("Sending note off")
    client.send_message(f"{path_prefix}/gate", 0)
    
    # Send additional "safety" messages to ensure note stops
    client.send_message(f"{path_prefix}/allNotesOff", 1)
    client.send_message(f"{path_prefix}/panic", 1)
    
    print("Done!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
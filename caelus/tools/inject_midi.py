#!/usr/bin/env python3
"""
Inject MIDI-like OSC messages directly to the router.
This script sends OSC messages that simulate MIDI input to the router port.
"""

import argparse
import sys
import time
from pythonosc import udp_client

def midi_to_freq(note):
    """Convert MIDI note number to frequency in Hz"""
    return 440.0 * (2 ** ((note - 69) / 12))

def main():
    """Send OSC messages to simulate MIDI input"""
    parser = argparse.ArgumentParser(description="Inject MIDI-like OSC messages to router")
    parser.add_argument("-p", "--port", type=int, default=9000,
                      help="Router OSC port (default: 9000)")
    parser.add_argument("-m", "--mode", type=str, default="scale",
                      choices=["scale", "chord", "single", "direct"],
                      help="What to play (default: scale)")
    parser.add_argument("-n", "--note", type=int, default=60,
                      help="MIDI note number for 'single' mode (default: 60)")
    parser.add_argument("-d", "--direct-port", type=int, default=5510,
                      help="Direct synth port for 'direct' mode (default: 5510)")
    parser.add_argument("-s", "--synth-name", type=str, default="simple",
                      help="Synth name for 'direct' mode (default: simple)")
    
    args = parser.parse_args()
    
    # Create OSC client for router
    router_client = udp_client.SimpleUDPClient("127.0.0.1", args.port)
    print(f"Connected to router at 127.0.0.1:{args.port}")
    
    # Create OSC client for direct synth communication if needed
    if args.mode == "direct":
        synth_client = udp_client.SimpleUDPClient("127.0.0.1", args.direct_port)
        print(f"Connected directly to synth at 127.0.0.1:{args.direct_port}")
    
    try:
        if args.mode == "scale":
            # Play a C major scale
            print("Playing C major scale...")
            notes = [60, 62, 64, 65, 67, 69, 71, 72, 
                    72, 71, 69, 67, 65, 64, 62, 60]
            
            for note in notes:
                # Send note on
                print(f"Sending note_on: {note}")
                router_client.send_message("/router/note_on", [note, 0.8])
                time.sleep(0.3)
                
                # Send note off
                print(f"Sending note_off: {note}")
                router_client.send_message("/router/note_off", [note])
                time.sleep(0.1)
                
        elif args.mode == "chord":
            # Play a C major chord
            print("Playing C major chord...")
            
            # Send chord notes
            print("Sending chord notes (C-E-G)...")
            router_client.send_message("/router/note_on", [60, 0.8])  # C
            time.sleep(0.05)
            router_client.send_message("/router/note_on", [64, 0.8])  # E
            time.sleep(0.05)
            router_client.send_message("/router/note_on", [67, 0.8])  # G
            
            # Hold for 2 seconds
            time.sleep(2.0)
            
            # Send note offs
            print("Sending note offs...")
            router_client.send_message("/router/note_off", [60])
            time.sleep(0.05)
            router_client.send_message("/router/note_off", [64])
            time.sleep(0.05)
            router_client.send_message("/router/note_off", [67])
            
        elif args.mode == "single":
            # Play a single note
            note = args.note
            print(f"Playing single note: {note}")
            
            # Send note on
            print(f"Sending note_on: {note}")
            router_client.send_message("/router/note_on", [note, 0.8])
            
            # Hold for 2 seconds
            time.sleep(2.0)
            
            # Send note off
            print(f"Sending note_off: {note}")
            router_client.send_message("/router/note_off", [note])
            
        elif args.mode == "direct":
            # Send OSC directly to the synth (bypassing router)
            print(f"Sending direct OSC to synth on port {args.direct_port}...")
            
            # Format OSC path with synth name
            path_prefix = f"/{args.synth_name}"
            
            # Send a note
            note = args.note
            freq = midi_to_freq(note)
            print(f"Playing note {note} ({freq:.2f} Hz) directly to synth...")
            
            # Send note parameters
            print(f"Sending {path_prefix}/freq = {freq}")
            synth_client.send_message(f"{path_prefix}/freq", freq)
            
            print(f"Sending {path_prefix}/gain = 0.8")
            synth_client.send_message(f"{path_prefix}/gain", 0.8)
            
            print(f"Sending {path_prefix}/gate = 1")
            synth_client.send_message(f"{path_prefix}/gate", 1)
            
            # Hold for 2 seconds
            time.sleep(2.0)
            
            # Send note off
            print(f"Sending {path_prefix}/gate = 0")
            synth_client.send_message(f"{path_prefix}/gate", 0)
            
        
        # Send all notes off at the end
        if args.mode != "direct":
            print("Sending all_notes_off")
            router_client.send_message("/router/all_notes_off", [])
        
        print("Done.")
        return 0
        
    except KeyboardInterrupt:
        print("\nInterrupted!")
        
        # Send all notes off
        if args.mode != "direct":
            print("Sending all_notes_off")
            router_client.send_message("/router/all_notes_off", [])
        elif args.mode == "direct":
            path_prefix = f"/{args.synth_name}"
            print(f"Sending {path_prefix}/gate = 0")
            synth_client.send_message(f"{path_prefix}/gate", 0)
            
        return 1

if __name__ == "__main__":
    sys.exit(main())
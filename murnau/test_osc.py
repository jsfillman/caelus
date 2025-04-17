#!/usr/bin/env python3
"""
OSC test utility for Faust synths
Sends test messages to verify synth is responding
"""
import argparse
import time
from pythonosc import udp_client

def main():
    parser = argparse.ArgumentParser(description='Test OSC communication with Faust synth')
    parser.add_argument('--osc-ip', default='127.0.0.1', help='OSC server IP address')
    parser.add_argument('--osc-port', type=int, default=5510, help='OSC server port')
    parser.add_argument('--synth-name', default='minimono', help='Synth name')
    args = parser.parse_args()
    
    # Create OSC client
    osc_client = udp_client.SimpleUDPClient(args.osc_ip, args.osc_port)
    
    print(f"Sending test OSC messages to {args.osc_ip}:{args.osc_port}")
    print(f"Synth: {args.synth_name}")
    print("Press Ctrl+C to stop")
    
    # Play a simple sequence
    try:
        # List of frequencies to play (C major scale)
        frequencies = [261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88, 523.25]
        
        # Set initial parameters
        print("Setting initial parameters...")
        osc_client.send_message(f"/{args.synth_name}/gain", 0.8)
        osc_client.send_message(f"/{args.synth_name}/filter_cutoff", 2000)
        osc_client.send_message(f"/{args.synth_name}/filter_resonance", 0.6)
        osc_client.send_message(f"/{args.synth_name}/osc1_level", 0.8)
        osc_client.send_message(f"/{args.synth_name}/osc2_level", 0.6)
        osc_client.send_message(f"/{args.synth_name}/osc3_level", 0.4)
        
        print("Playing test sequence...")
        while True:
            for freq in frequencies:
                # Set frequency
                osc_client.send_message(f"/{args.synth_name}/freq", freq)
                
                # Note on
                osc_client.send_message(f"/{args.synth_name}/gate", 1)
                print(f"Note ON: {freq} Hz")
                
                # Hold note
                time.sleep(0.3)
                
                # Note off
                osc_client.send_message(f"/{args.synth_name}/gate", 0)
                print(f"Note OFF: {freq} Hz")
                
                # Pause between notes
                time.sleep(0.1)
                
            # Pause between sequences
            print("Sequence complete, repeating...")
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping...")
        # Make sure gate is off
        osc_client.send_message(f"/{args.synth_name}/gate", 0)
        print("Done")

if __name__ == "__main__":
    main()
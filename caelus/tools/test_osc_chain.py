#!/usr/bin/env python3
"""
Test OSC Chain

This script performs a comprehensive test of the OSC chain from MIDI to synth.
It tests each component individually to identify where the chain is breaking.

Tests performed:
1. Direct synth communication (bypassing router)
2. Router communication
3. Full MIDI-OSC-synth chain

Each test plays a different melody pattern to help identify which step succeeded.
"""

import argparse
import sys
import time
import subprocess
import os
from pythonosc import udp_client

def midi_to_freq(note):
    """Convert MIDI note number to frequency in Hz"""
    return 440.0 * (2 ** ((note - 69) / 12))

def play_direct_to_synth(synth_port, synth_name, melody_name="arpeggio"):
    """Play notes directly to the synth, bypassing the router"""
    print(f"\n=== TEST 1: Direct Synth Communication (port {synth_port}) ===")
    
    try:
        # Create OSC client for direct synth communication
        synth_client = udp_client.SimpleUDPClient("127.0.0.1", synth_port)
        print(f"Connected directly to synth at 127.0.0.1:{synth_port}")
        
        # OSC path with synth name
        path_prefix = f"/{synth_name}"
        
        # Choose melody based on name
        if melody_name == "arpeggio":
            notes = [60, 64, 67, 72, 67, 64, 60]  # C major arpeggio
            durations = [0.3, 0.3, 0.3, 0.5, 0.3, 0.3, 0.5]
        elif melody_name == "scale":
            notes = [60, 62, 64, 65, 67, 69, 71, 72]  # C major scale
            durations = [0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.5]
        else:  # default to simple pattern
            notes = [60, 64, 67, 60]  # C major chord tones
            durations = [0.3, 0.3, 0.3, 0.5]
        
        print(f"Playing {melody_name} melody pattern directly to synth...")
        
        # Play each note in sequence
        for i, (note, duration) in enumerate(zip(notes, durations)):
            # Convert to frequency
            freq = midi_to_freq(note)
            
            # Send note parameters
            print(f"[{i+1}/{len(notes)}] Note {note} ({freq:.2f} Hz)")
            synth_client.send_message(f"{path_prefix}/freq", freq)
            synth_client.send_message(f"{path_prefix}/gain", 0.8)
            synth_client.send_message(f"{path_prefix}/gate", 1)
            
            # Hold for duration
            time.sleep(duration)
            
            # Send note off
            synth_client.send_message(f"{path_prefix}/gate", 0)
            time.sleep(0.05)  # Brief pause between notes
        
        # Ensure note is off at the end
        synth_client.send_message(f"{path_prefix}/allNotesOff", 1)
        
        print("TEST 1 COMPLETE - Did you hear the melody?")
        
        response = input("Did you hear sound? (y/n): ").strip().lower()
        return response.startswith('y')
        
    except Exception as e:
        print(f"Error in direct synth test: {e}")
        return False

def play_through_router(router_port, melody_name="chord"):
    """Play notes through the router, which should forward to the synth"""
    print(f"\n=== TEST 2: Router Communication (port {router_port}) ===")
    
    try:
        # Create OSC client for router
        router_client = udp_client.SimpleUDPClient("127.0.0.1", router_port)
        print(f"Connected to router at 127.0.0.1:{router_port}")
        
        # Choose melody based on name
        if melody_name == "chord":
            # Play a C major chord with each note entering sequentially
            print("Playing chord pattern through router...")
            
            # Send chord notes one at a time
            print("Sending C note (60)...")
            router_client.send_message("/router/note_on", [60, 0.8])  # C
            time.sleep(0.5)
            
            print("Adding E note (64)...")
            router_client.send_message("/router/note_on", [64, 0.8])  # E
            time.sleep(0.5)
            
            print("Adding G note (67)...")
            router_client.send_message("/router/note_on", [67, 0.8])  # G
            time.sleep(1.5)
            
            # Turn off notes one at a time
            print("Releasing G note (67)...")
            router_client.send_message("/router/note_off", [67])
            time.sleep(0.5)
            
            print("Releasing E note (64)...")
            router_client.send_message("/router/note_off", [64])
            time.sleep(0.5)
            
            print("Releasing C note (60)...")
            router_client.send_message("/router/note_off", [60])
            
        elif melody_name == "pentatonic":
            # Play a C minor pentatonic scale (different from other tests)
            notes = [60, 63, 65, 67, 70, 72]
            
            print("Playing pentatonic scale through router...")
            for note in notes:
                print(f"Sending note_on: {note}")
                router_client.send_message("/router/note_on", [note, 0.8])
                time.sleep(0.3)
                
                print(f"Sending note_off: {note}")
                router_client.send_message("/router/note_off", [note])
                time.sleep(0.1)
                
        else:  # default pattern
            # Play a simple alternating pattern
            print("Playing alternating pattern through router...")
            for _ in range(4):
                # High note
                router_client.send_message("/router/note_on", [72, 0.8])
                time.sleep(0.25)
                router_client.send_message("/router/note_off", [72])
                time.sleep(0.1)
                
                # Low note
                router_client.send_message("/router/note_on", [60, 0.8])
                time.sleep(0.25)
                router_client.send_message("/router/note_off", [60])
                time.sleep(0.1)
        
        # Send all notes off at the end
        router_client.send_message("/router/all_notes_off", [])
        
        print("TEST 2 COMPLETE - Did you hear the melody?")
        
        response = input("Did you hear sound? (y/n): ").strip().lower()
        return response.startswith('y')
        
    except Exception as e:
        print(f"Error in router test: {e}")
        return False

def check_port_in_use(port):
    """Check if a port is in use"""
    try:
        if sys.platform == 'darwin':  # macOS
            result = subprocess.run(['lsof', '-i', f':{port}'], 
                                  capture_output=True, text=True)
            return bool(result.stdout)
        else:  # Linux/Unix
            result = subprocess.run(['netstat', '-tln'], 
                                  capture_output=True, text=True)
            return str(port) in result.stdout
    except Exception:
        # If we can't check, assume it's not in use
        return False

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Test the OSC chain from MIDI to synth")
    parser.add_argument("--router-port", type=int, default=9000,
                       help="Router OSC port (default: 9000)")
    parser.add_argument("--synth-port", type=int, default=5510,
                       help="Synth OSC port (default: 5510)")
    parser.add_argument("--synth-name", type=str, default="simple",
                       help="Synth name from voices.yaml (default: simple)")
    parser.add_argument("--skip-direct", action="store_true",
                       help="Skip the direct synth test")
    parser.add_argument("--skip-router", action="store_true",
                       help="Skip the router test")
    
    args = parser.parse_args()
    
    print("=== OSC Chain Test ===")
    print(f"Router port: {args.router_port}")
    print(f"Synth port: {args.synth_port}")
    print(f"Synth name: {args.synth_name}")
    
    # Check if ports are in use
    router_in_use = check_port_in_use(args.router_port)
    synth_in_use = check_port_in_use(args.synth_port)
    
    print(f"Router port in use: {router_in_use}")
    print(f"Synth port in use: {synth_in_use}")
    
    # Track test results
    results = {
        "direct_synth": None,
        "router": None
    }
    
    # Test 1: Direct synth communication
    if not args.skip_direct:
        results["direct_synth"] = play_direct_to_synth(args.synth_port, args.synth_name)
    else:
        print("\nSkipping direct synth test as requested.")
    
    # Test 2: Router communication
    if not args.skip_router:
        results["router"] = play_through_router(args.router_port)
    else:
        print("\nSkipping router test as requested.")
    
    # Summarize results
    print("\n=== TEST RESULTS ===")
    
    if results["direct_synth"] is not None:
        print(f"Direct synth communication: {'PASSED' if results['direct_synth'] else 'FAILED'}")
    else:
        print("Direct synth communication: SKIPPED")
        
    if results["router"] is not None:
        print(f"Router communication: {'PASSED' if results['router'] else 'FAILED'}")
    else:
        print("Router communication: SKIPPED")
    
    # Diagnostic summary
    print("\n=== DIAGNOSIS ===")
    
    if results["direct_synth"] and not results["router"]:
        print("The synth is responding correctly to direct OSC messages, but")
        print("messages sent through the router are not reaching the synth.")
        print("\nPossible issues:")
        print("1. The router is not forwarding messages correctly")
        print("2. The voice allocation in the router is not working")
        print("3. The router is sending messages with an incorrect OSC path format")
        print("\nRecommendations:")
        print("1. Check the voices.yaml file to ensure synth_name and port are correct")
        print("2. Verify that the fix in voice.py for OSC path formatting is correct")
        print("3. Add more debug logging in the router to see if it's receiving and processing messages")
        
    elif not results["direct_synth"] and not results["router"]:
        print("Neither direct synth communication nor router communication is working.")
        print("\nPossible issues:")
        print("1. The synth is not running or is not listening on the expected port")
        print("2. The synth_name in voices.yaml doesn't match what the synth expects")
        print("3. The audio backend (JACK) is not properly configured")
        print("\nRecommendations:")
        print("1. Check if the synth process is running (ps aux | grep synth)")
        print("2. Verify the synth port is correct (netstat -an | grep 5510)")
        print("3. Check the audio backend with tools/check_audio_system.py")
        
    elif results["direct_synth"] and results["router"]:
        print("Both direct synth communication and router communication are working!")
        print("If you're not hearing sound when playing MIDI notes in Caelus, the issue may be:")
        print("1. MIDI input is not being received correctly")
        print("2. The MIDI-OSC bridge is not forwarding MIDI messages to the router")
        print("\nRecommendations:")
        print("1. Check MIDI input in the Caelus UI (MIDI tab)")
        print("2. Add debug logging in the MIDI-OSC bridge to verify messages are being processed")
        
    elif not results["direct_synth"] and results["router"]:
        print("Strangely, router communication is working but direct synth communication is not.")
        print("This is an unexpected result that suggests something unusual in the setup.")
        print("\nPossible issues:")
        print("1. The synth port specified for direct communication is incorrect")
        print("2. The synth_name used for direct communication is incorrect")
        print("\nRecommendations:")
        print("1. Double check the synth port and name in the voices.yaml file")
        print("2. Try running the direct test again with different parameters")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
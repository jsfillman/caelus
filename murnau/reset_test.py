#!/usr/bin/env python3

"""
Reset and test the JACK + Faust setup with maximum debug info
"""

import subprocess
import os
import signal
import sys
import time

def run_cmd(cmd, description=None):
    """Run a command and print its output"""
    if description:
        print(f"\n=== {description} ===")
    
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    
    print("STDOUT:")
    print(result.stdout)
    
    if result.stderr:
        print("STDERR:")
        print(result.stderr)
    
    print(f"Return code: {result.returncode}")
    return result

def restart_jack():
    """Kill and restart JACK with verbose output"""
    # Kill any existing JACK processes
    run_cmd("killall jackd jackdmp", "Stopping JACK")
    time.sleep(1)
    
    # Start JACK with default device and verbose output
    jack_cmd = "jackd -d coreaudio -d 'Built-in Output' -v"
    print(f"\n=== Starting JACK: {jack_cmd} ===")
    print("Press Ctrl+C when JACK is running to continue...")
    
    try:
        # Run JACK in the foreground so we can see output
        subprocess.run(jack_cmd, shell=True)
    except KeyboardInterrupt:
        print("\nJACK startup interrupted, continuing...")

def compile_and_start_synth():
    """Compile and start the synth with maximum debugging"""
    # Compile with OSC support
    run_cmd("faust2jackconsole -osc minimono.dsp", "Compiling synth")
    
    # Generate JSON
    run_cmd("faust -json -o minimono.dsp.json minimono.dsp", "Generating JSON")
    
    # Start synth with OSC and verbose output
    synth_cmd = "./minimono --control 1 -v"
    print(f"\n=== Starting synth: {synth_cmd} ===")
    print("Press Ctrl+C when synth is running to continue...")
    
    try:
        # Run synth in the foreground
        subprocess.run(synth_cmd, shell=True)
    except KeyboardInterrupt:
        print("\nSynth startup interrupted, continuing...")

def check_connections():
    """Check and fix JACK connections"""
    # List ports
    run_cmd("jack_lsp -c", "JACK ports")
    
    # Make sure synth is connected to outputs
    print("\n=== Connecting synth to outputs ===")
    subprocess.run("jack_connect minimono:out_0 system:playback_1", shell=True)
    subprocess.run("jack_connect minimono:out_0 system:playback_2", shell=True)
    
    # Check connections again
    run_cmd("jack_lsp -c", "Updated JACK connections")

def send_test_notes():
    """Send test notes using oscsend if available"""
    if subprocess.run("which oscsend", shell=True, capture_output=True).returncode == 0:
        print("\n=== Sending test notes with oscsend ===")
        # Set max volume
        subprocess.run("oscsend localhost 5510 /minimono/gain f 1.0", shell=True)
        
        # Play a note
        subprocess.run("oscsend localhost 5510 /minimono/freq f 440.0", shell=True)
        subprocess.run("oscsend localhost 5510 /minimono/gate f 1.0", shell=True)
        time.sleep(1)
        subprocess.run("oscsend localhost 5510 /minimono/gate f 0.0", shell=True)
    else:
        print("\n=== oscsend not available, skipping OSC test ===")
        print("Run 'brew install oscsend' to install this tool")

def main():
    print("=== Faust + JACK Reset and Test ===")
    print("This script will reset your JACK setup and test the synth.")
    print("You'll need to interrupt with Ctrl+C after each step.")
    
    # Ask for confirmation
    response = input("Continue? (y/n): ").strip().lower()
    if response != 'y':
        print("Aborted.")
        return
    
    # Step 1: Restart JACK
    restart_jack()
    
    # Step 2: Compile and start synth
    compile_and_start_synth()
    
    # Step 3: Check and fix connections
    check_connections()
    
    # Step 4: Send test notes
    send_test_notes()
    
    print("\n=== Test complete ===")
    print("If you still don't hear sound, check:")
    print("1. System volume is up")
    print("2. JACK is using the correct audio device")
    print("3. No other audio apps are blocking the device")
    print("4. Faust synth code is generating audio correctly")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Test script to run the OSC router and validate MIDI reception
"""
import os
import sys
import time
import subprocess
import threading
from pythonosc import udp_client

# Configuration
OSC_IP = "127.0.0.1"
OSC_PORT = 9001
ROUTER_NAME = "router"
VOICES_FILE = "presets/simple/voices.yaml"

def monitor_process(proc, name):
    """Monitor process output"""
    while proc.poll() is None:
        stdout_line = proc.stdout.readline()
        if stdout_line:
            print(f"{name} STDOUT: {stdout_line.rstrip()}")
        stderr_line = proc.stderr.readline()
        if stderr_line:
            print(f"{name} STDERR: {stderr_line.rstrip()}")
    print(f"Process {name} exited with code {proc.returncode}")

def main():
    # Check if OSC router file exists
    if not os.path.exists("osc_router.py"):
        print("ERROR: osc_router.py not found!")
        return 1
        
    # Check if voices file exists
    if not os.path.exists(VOICES_FILE):
        print(f"ERROR: Voices file {VOICES_FILE} not found!")
        return 1

    # Start OSC router
    print(f"Starting OSC router with config: {VOICES_FILE}")
    router_cmd = ["python3", "osc_router.py", "-c", VOICES_FILE, "-p", str(OSC_PORT)]
    
    router_proc = subprocess.Popen(
        router_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        bufsize=1
    )
    
    # Monitor router output
    monitor_thread = threading.Thread(
        target=monitor_process, 
        args=(router_proc, "OSC ROUTER"), 
        daemon=True
    )
    monitor_thread.start()
    
    # Wait for router to initialize
    print("Waiting for OSC router to initialize...")
    time.sleep(3)
    
    # Create OSC client
    print(f"Creating OSC client to {OSC_IP}:{OSC_PORT}")
    osc = udp_client.SimpleUDPClient(OSC_IP, OSC_PORT)
    
    # Test sequence
    print("\nRunning OSC communication tests...")
    
    print("\nTest 1: All notes off")
    osc.send_message(f"/{ROUTER_NAME}/all_notes_off", [])
    time.sleep(0.5)
    
    print("\nTest 2: Note on")
    osc.send_message(f"/{ROUTER_NAME}/note_on", [60, 0.8])  # Middle C, velocity 0.8
    time.sleep(1)
    
    print("\nTest 3: Note off")
    osc.send_message(f"/{ROUTER_NAME}/note_off", [60])
    time.sleep(0.5)
    
    print("\nTest 4: CC message (modulation wheel)")
    osc.send_message(f"/{ROUTER_NAME}/cc", [1, 0.5])  # CC 1 (mod wheel), value 0.5
    time.sleep(0.5)
    
    print("\nTest 5: Parameter control")
    osc.send_message(f"/{ROUTER_NAME}/param_all/cutoff", ["cutoff", 2000])
    time.sleep(0.5)
    
    print("\nTest 6: Poly aftertouch")
    osc.send_message(f"/{ROUTER_NAME}/poly_aftertouch", [60, 0.7])
    time.sleep(0.5)
    
    print("\nTest 7: Pitch bend")
    osc.send_message(f"/{ROUTER_NAME}/pitch_bend", [0.5])
    time.sleep(0.5)
    
    print("\nAll test messages sent. Check the router logs above.")
    print("Press Ctrl+C to exit.")
    
    try:
        # Keep running and monitor the router
        while True:
            if router_proc.poll() is not None:
                print(f"Router process exited with code {router_proc.returncode}")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        if router_proc.poll() is None:
            print("Terminating router process...")
            router_proc.terminate()
            try:
                router_proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                router_proc.kill()
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 
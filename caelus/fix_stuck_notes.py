#!/usr/bin/env python3
"""
Stuck Note Monitor - Watches for and cleans up stuck MIDI notes
"""
import sys
import time
import threading
import json
from pythonosc import udp_client
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer

# Configuration
OSC_IP = "127.0.0.1"
OSC_PORT = 9001  # Match our updated port
ROUTER_NAME = "router"
MONITOR_PORT = 9200  # Port for receiving status updates
CHECK_INTERVAL = 5.0  # Seconds between checks for stuck notes
MAX_NOTE_DURATION = 15.0  # Maximum seconds a note should stay on

# Track active notes and their start times
active_notes = {}  # {note_number: start_time}
lock = threading.Lock()  # Thread safety

# Set up OSC client
osc = udp_client.SimpleUDPClient(OSC_IP, OSC_PORT)

def send_osc(address, value):
    """Send OSC message and handle errors"""
    try:
        print(f"Sending OSC: {address} {value}")
        osc.send_message(address, value)
        return True
    except Exception as e:
        print(f"ERROR sending OSC message: {e}")
        return False

def handle_active_notes(address, *args):
    """Handle active notes updates from router"""
    try:
        note_data = json.loads(args[0])
        current_time = time.time()
        
        with lock:
            # Add newly detected notes with current timestamp
            for note in note_data:
                note = int(note)
                if note not in active_notes:
                    active_notes[note] = current_time
                    print(f"Note {note} added to tracking")
    except Exception as e:
        print(f"Error handling active notes: {e}")

def clear_stuck_notes():
    """Check for and clear notes that have been on too long"""
    while True:
        time.sleep(CHECK_INTERVAL)
        current_time = time.time()
        notes_to_clear = []
        
        # Ask router for current active notes
        send_osc(f"/router/get", "voice_manager/active_notes")
        time.sleep(0.1)  # Wait for response to be processed
        
        # Check for stuck notes
        with lock:
            for note, start_time in active_notes.items():
                duration = current_time - start_time
                if duration > MAX_NOTE_DURATION:
                    print(f"Note {note} has been on for {duration:.1f}s - clearing")
                    notes_to_clear.append(note)
        
        # Send note-offs for stuck notes
        for note in notes_to_clear:
            send_osc(f"/{ROUTER_NAME}/note_off", [note])
            with lock:
                if note in active_notes:
                    del active_notes[note]

def main():
    # Set up dispatcher for OSC messages
    dispatcher = Dispatcher()
    dispatcher.map("/router/value/voice_manager/active_notes", handle_active_notes)
    
    # Start OSC server to receive updates
    try:
        server = ThreadingOSCUDPServer((OSC_IP, MONITOR_PORT), dispatcher)
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        print(f"Monitoring OSC on port {MONITOR_PORT}")
    except Exception as e:
        print(f"Error starting OSC server: {e}")
        return 1
    
    # Start stuck note monitor thread
    monitor_thread = threading.Thread(target=clear_stuck_notes)
    monitor_thread.daemon = True
    monitor_thread.start()
    
    print(f"Stuck note monitor running. Will clear notes after {MAX_NOTE_DURATION} seconds.")
    print("Request active notes every 5 seconds")
    
    # Main loop to keep the script running and periodically check for active notes
    try:
        while True:
            # Ask for current active notes
            send_osc(f"/router/get", "voice_manager/active_notes")
            time.sleep(5)
    except KeyboardInterrupt:
        print("\nShutting down...")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 
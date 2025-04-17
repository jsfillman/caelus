#!/usr/bin/env python3
"""
Direct OSC interface for multi_synth - like a virtual keyboard
"""
import socket
import time
import struct
import sys
import curses

def send_osc(ip, port, address, value):
    """Send an OSC message with a float value"""
    # Format OSC message
    address_bytes = address.encode('utf-8')
    address_padded = address_bytes + (b'\0' * (4 - len(address_bytes) % 4))
    
    # Format type tag
    type_tag = b',f'
    type_tag_padded = type_tag + (b'\0' * (4 - len(type_tag) % 4))
    
    # Format float value
    value_bytes = struct.pack('>f', float(value))
    
    # Complete message
    message = address_padded + type_tag_padded + value_bytes
    
    # Send via UDP
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(message, (ip, port))
    sock.close()

def curses_interface(stdscr, ip="127.0.0.1", port=5510, synth_name="multi_synth"):
    """Interactive curses interface for controlling synth"""
    # Set up curses
    curses.curs_set(0)
    stdscr.nodelay(1)
    stdscr.timeout(100)
    
    # Define MIDI note to frequency mapping
    def note_to_freq(note):
        return 440.0 * (2.0 ** ((note - 69) / 12.0))
    
    # Notes (C3 to C4 = computer keyboard keys 'a' through 'k')
    note_map = {
        'a': 48,  # C3
        'w': 49,  # C#3
        's': 50,  # D3
        'e': 51,  # D#3
        'd': 52,  # E3
        'f': 53,  # F3
        't': 54,  # F#3
        'g': 55,  # G3
        'y': 56,  # G#3
        'h': 57,  # A3
        'u': 58,  # A#3
        'j': 59,  # B3
        'k': 60,  # C4
        'o': 61,  # C#4
        'l': 62,  # D4
        'p': 63,  # D#4
        ';': 64,  # E4
    }
    
    # Set initial parameters
    current_gain = 1.0
    current_wave = 3  # Square
    current_filter = 0  # Off
    current_cutoff = 8000
    current_resonance = 0.3
    
    # Apply initial settings
    send_osc(ip, port, f"/{synth_name}/gain", current_gain)
    send_osc(ip, port, f"/{synth_name}/wave_type", current_wave)
    send_osc(ip, port, f"/{synth_name}/filter_on", current_filter)
    send_osc(ip, port, f"/{synth_name}/cutoff", current_cutoff)
    send_osc(ip, port, f"/{synth_name}/resonance", current_resonance)
    send_osc(ip, port, f"/{synth_name}/attack", 0.01)
    send_osc(ip, port, f"/{synth_name}/release", 0.5)
    
    # Keep track of active notes
    active_notes = set()
    
    # Wave type names
    wave_names = ["Sine", "Triangle", "Sawtooth", "Square"]
    
    # Main loop
    running = True
    while running:
        # Clear screen
        stdscr.clear()
        
        # Draw interface
        stdscr.addstr(0, 0, "Direct OSC Control - Virtual Keyboard")
        stdscr.addstr(1, 0, f"Sending to: {ip}:{port}/{synth_name}")
        stdscr.addstr(3, 0, f"Gain: {current_gain:.1f} (up/down to change)")
        stdscr.addstr(4, 0, f"Wave: {wave_names[current_wave]} (1-4 to change)")
        stdscr.addstr(5, 0, f"Filter: {'ON' if current_filter else 'OFF'} (F to toggle)")
        stdscr.addstr(6, 0, f"Cutoff: {current_cutoff} (left/right to change)")
        stdscr.addstr(7, 0, f"Resonance: {current_resonance:.1f} ([/] to change)")
        
        stdscr.addstr(9, 0, "Notes: A S D F G H J K L ; (Piano keys - hold to play)")
        stdscr.addstr(10, 0, f"Active notes: {len(active_notes)}")
        
        stdscr.addstr(12, 0, "Press Q to quit")
        
        # Get input
        try:
            key = stdscr.getkey().lower()
        except:
            key = None
        
        if key:
            # Handle quit
            if key == 'q':
                running = False
            
            # Handle note on
            elif key in note_map and note_map[key] not in active_notes:
                note = note_map[key]
                freq = note_to_freq(note)
                send_osc(ip, port, f"/{synth_name}/freq", freq)
                send_osc(ip, port, f"/{synth_name}/gate", 1.0)
                active_notes.add(note)
                stdscr.addstr(14, 0, f"Note ON: {note} ({freq:.1f} Hz)   ")
            
            # Handle gain changes
            elif key == 'key_up':
                current_gain = min(1.0, current_gain + 0.1)
                send_osc(ip, port, f"/{synth_name}/gain", current_gain)
            elif key == 'key_down':
                current_gain = max(0.1, current_gain - 0.1)
                send_osc(ip, port, f"/{synth_name}/gain", current_gain)
            
            # Handle wave type changes
            elif key in ['1', '2', '3', '4']:
                current_wave = int(key) - 1
                send_osc(ip, port, f"/{synth_name}/wave_type", current_wave)
            
            # Handle filter toggle
            elif key == 'f':
                current_filter = 1 - current_filter
                send_osc(ip, port, f"/{synth_name}/filter_on", current_filter)
            
            # Handle cutoff changes
            elif key == 'key_right':
                current_cutoff = min(10000, current_cutoff + 500)
                send_osc(ip, port, f"/{synth_name}/cutoff", current_cutoff)
            elif key == 'key_left':
                current_cutoff = max(100, current_cutoff - 500)
                send_osc(ip, port, f"/{synth_name}/cutoff", current_cutoff)
            
            # Handle resonance changes
            elif key == '[':
                current_resonance = max(0.1, current_resonance - 0.1)
                send_osc(ip, port, f"/{synth_name}/resonance", current_resonance)
            elif key == ']':
                current_resonance = min(0.9, current_resonance + 0.1)
                send_osc(ip, port, f"/{synth_name}/resonance", current_resonance)
        
        # Check for key releases
        for note in list(active_notes):
            key_name = [k for k, v in note_map.items() if v == note][0]
            try:
                if stdscr.inch(20, ord(key_name) - ord('a')) & curses.A_CHAR != ord(key_name):
                    # Key not pressed anymore
                    send_osc(ip, port, f"/{synth_name}/gate", 0.0)
                    active_notes.remove(note)
                    stdscr.addstr(14, 0, f"Note OFF: {note}   ")
            except:
                pass  # Not all keys may be mappable
        
        # Check if any notes are still active
        if active_notes:
            stdscr.addstr(15, 0, "◉ PLAYING")
        else:
            stdscr.addstr(15, 0, "○ IDLE")
        
        # Refresh screen
        stdscr.refresh()
    
    # Turn off any active notes before exiting
    if active_notes:
        send_osc(ip, port, f"/{synth_name}/gate", 0.0)

def main():
    # Get arguments
    ip = "127.0.0.1"
    port = 5510
    synth_name = "multi_synth"
    
    if len(sys.argv) > 1:
        synth_name = sys.argv[1]
    
    print(f"Starting direct OSC control for {synth_name}")
    print("Make sure synth is running with: ./multi_synth --control 1")
    
    try:
        # Start curses interface
        curses.wrapper(curses_interface, ip, port, synth_name)
    except Exception as e:
        print(f"Error: {e}")
    
    print("Direct OSC control exited")

if __name__ == "__main__":
    main()
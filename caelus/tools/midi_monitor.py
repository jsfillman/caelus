#!/usr/bin/env python3
"""
MIDI Monitor

This script monitors MIDI input and shows what messages are being received.
Use this to verify MIDI input is working correctly.
"""

import argparse
import sys
import time
from datetime import datetime
import signal

def list_midi_ports():
    """List available MIDI input ports"""
    try:
        import mido
        ports = mido.get_input_names()
        if ports:
            print("Available MIDI ports:")
            for i, port in enumerate(ports):
                print(f"  {i+1}: {port}")
            return ports
        else:
            print("No MIDI ports found.")
            return []
    except ImportError:
        print("Error: mido not installed. Cannot list MIDI ports.")
        print("Try: pip install mido python-rtmidi")
        return []
    except Exception as e:
        print(f"Error listing MIDI ports: {e}")
        return []

def monitor_midi(port_name, verbose=False):
    """Monitor MIDI input from specified port"""
    try:
        import mido
        
        print(f"Monitoring MIDI input from: {port_name}")
        print("Press Ctrl+C to stop.")
        
        # Track session stats
        stats = {
            "note_on": 0,
            "note_off": 0,
            "control_change": 0,
            "other": 0,
            "total": 0,
            "start_time": datetime.now()
        }
        
        # Set up signal handler for clean exit
        def signal_handler(sig, frame):
            # Calculate duration
            duration = datetime.now() - stats["start_time"]
            duration_secs = duration.total_seconds()
            
            # Print summary
            print("\n\n=== MIDI Monitoring Summary ===")
            print(f"Duration: {duration_secs:.1f} seconds")
            print(f"Total messages: {stats['total']}")
            print(f"Note on: {stats['note_on']}")
            print(f"Note off: {stats['note_off']}")
            print(f"Control change: {stats['control_change']}")
            print(f"Other: {stats['other']}")
            print(f"Messages per second: {stats['total']/duration_secs:.1f}")
            sys.exit(0)
            
        signal.signal(signal.SIGINT, signal_handler)
        
        # Open MIDI port
        with mido.open_input(port_name) as midi_in:
            print(f"Successfully opened MIDI port: {port_name}")
            
            # Process MIDI messages
            while True:
                for msg in midi_in.iter_pending():
                    # Update stats
                    stats["total"] += 1
                    if msg.type == 'note_on':
                        stats["note_on"] += 1
                    elif msg.type == 'note_off':
                        stats["note_off"] += 1
                    elif msg.type == 'control_change':
                        stats["control_change"] += 1
                    else:
                        stats["other"] += 1
                    
                    # Get timestamp
                    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    
                    # Print message details
                    if msg.type == 'note_on':
                        # Format velocity as 0-1.0 (for comparison with OSC)
                        vel_norm = msg.velocity / 127.0
                        print(f"[{timestamp}] Note ON: {msg.note} (vel: {msg.velocity}, norm: {vel_norm:.2f})")
                        
                        # Show OSC equivalent in verbose mode
                        if verbose:
                            print(f"  → OSC: /router/note_on [{msg.note}, {vel_norm:.2f}]")
                            
                    elif msg.type == 'note_off':
                        print(f"[{timestamp}] Note OFF: {msg.note} (vel: {msg.velocity})")
                        
                        # Show OSC equivalent in verbose mode
                        if verbose:
                            print(f"  → OSC: /router/note_off [{msg.note}]")
                            
                    elif msg.type == 'control_change':
                        # Special handling for common CCs
                        if msg.control == 64:
                            state = "ON" if msg.value >= 64 else "OFF"
                            print(f"[{timestamp}] Sustain pedal {state} (CC 64: {msg.value})")
                            
                            # Show OSC equivalent in verbose mode
                            if verbose:
                                print(f"  → OSC: /router/sustain [{1 if state == 'ON' else 0}]")
                                
                        elif msg.control == 1:
                            print(f"[{timestamp}] Mod wheel: {msg.value} ({msg.value/127.0:.2f})")
                            
                            # Show OSC equivalent in verbose mode
                            if verbose:
                                print(f"  → OSC: /router/cc [1, {msg.value}]")
                                
                        else:
                            print(f"[{timestamp}] CC {msg.control}: {msg.value}")
                            
                            # Show OSC equivalent in verbose mode
                            if verbose:
                                print(f"  → OSC: /router/cc [{msg.control}, {msg.value}]")
                                
                    elif msg.type == 'pitchwheel':
                        # Normalize to -1 to 1 range
                        pitch_norm = msg.pitch / 8192.0
                        print(f"[{timestamp}] Pitch bend: {msg.pitch} (norm: {pitch_norm:.2f})")
                        
                        # Show OSC equivalent in verbose mode
                        if verbose:
                            print(f"  → OSC: /router/pitch_bend [{pitch_norm:.2f}]")
                            
                    else:
                        print(f"[{timestamp}] {msg}")
                    
                # Brief sleep to not hog CPU
                time.sleep(0.001)
                
    except ImportError:
        print("Error: mido not installed. Cannot monitor MIDI.")
        print("Try: pip install mido python-rtmidi")
        return False
    except Exception as e:
        print(f"Error monitoring MIDI: {e}")
        return False

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Monitor MIDI input")
    parser.add_argument("-l", "--list", action="store_true",
                      help="List available MIDI ports and exit")
    parser.add_argument("-p", "--port", type=str,
                      help="MIDI port to monitor")
    parser.add_argument("-v", "--verbose", action="store_true",
                      help="Show verbose output including OSC equivalents")
    
    args = parser.parse_args()
    
    # List MIDI ports if requested
    if args.list:
        list_midi_ports()
        return 0
    
    # If no port specified, list ports and prompt
    if not args.port:
        ports = list_midi_ports()
        if not ports:
            return 1
            
        # Prompt for port selection
        try:
            selection = input("\nSelect MIDI port (number or name): ")
            
            # Try to interpret as a number first
            try:
                port_idx = int(selection) - 1
                if 0 <= port_idx < len(ports):
                    selected_port = ports[port_idx]
                else:
                    print(f"Invalid selection: {selection}")
                    return 1
            except ValueError:
                # Not a number, use as port name
                if selection in ports:
                    selected_port = selection
                else:
                    print(f"Unknown port: {selection}")
                    return 1
                    
            # Monitor the selected port
            monitor_midi(selected_port, args.verbose)
            
        except KeyboardInterrupt:
            print("\nExiting...")
            return 0
    else:
        # Use specified port
        monitor_midi(args.port, args.verbose)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
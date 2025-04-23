#!/usr/bin/env python3
"""
Simplified MIDI to OSC bridge for testing
"""
import sys
import time
import mido
import threading
from pythonosc import udp_client

# --- Configuration ---
OSC_IP = "127.0.0.1"  # Use localhost instead of 0.0.0.0
OSC_PORT = 9000
ROUTER_NAME = "router"

def main():
    # List available MIDI ports
    try:
        ports = mido.get_input_names()
        print(f"Available MIDI ports: {ports}")
        
        if not ports:
            print("ERROR: No MIDI ports found!")
            return 1
            
    except Exception as e:
        print(f"ERROR listing MIDI ports: {e}")
        return 1

    # Select port
    if len(ports) == 1:
        port_name = ports[0]
        print(f"Auto-selecting only available port: {port_name}")
    else:
        print("\nPlease select a MIDI port:")
        for i, port in enumerate(ports):
            print(f"{i+1}. {port}")
        
        choice = input("Enter port number: ")
        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(ports):
                raise ValueError("Invalid selection")
            port_name = ports[idx]
        except ValueError:
            print("Invalid selection. Exiting.")
            return 1
    
    # Create OSC client
    print(f"Creating OSC client to {OSC_IP}:{OSC_PORT}")
    osc = udp_client.SimpleUDPClient(OSC_IP, OSC_PORT)
    
    # Handle MIDI messages
    def handle_midi(msg):
        print(f"MIDI: {msg}")
        address = f"/{ROUTER_NAME}/unknown"
        val = 0.0
        
        if msg.type == 'note_on':
            address = f"/{ROUTER_NAME}/note_on"
            val = [msg.note, msg.velocity / 127.0]
        elif msg.type == 'note_off':
            address = f"/{ROUTER_NAME}/note_off"
            val = [msg.note]
        elif msg.type == 'control_change':
            address = f"/{ROUTER_NAME}/cc"
            val = [msg.control, msg.value / 127.0]
        elif msg.type == 'polytouch':
            address = f"/{ROUTER_NAME}/poly_aftertouch"
            val = [msg.note, msg.value / 127.0]
        elif msg.type == 'pitchwheel':
            address = f"/{ROUTER_NAME}/pitch_bend"
            # Pitchwheel range is -8192 to 8191, normalize to -1.0 to 1.0
            val = [msg.pitch / 8192.0]
            
        print(f"Sending OSC: {address} {val}")
        try:
            osc.send_message(address, val)
            print("OSC sent successfully")
        except Exception as e:
            print(f"ERROR sending OSC: {e}")

    # Open MIDI port and process messages
    print(f"Opening MIDI port: {port_name}")
    try:
        with mido.open_input(port_name) as inport:
            print(f"Successfully opened {port_name}")
            print("Waiting for MIDI messages...")
            print("Play notes or move controllers...")
            print("(Press Ctrl+C to exit)")
            
            while True:
                for msg in inport.iter_pending():
                    handle_midi(msg)
                time.sleep(0.01)
                
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"ERROR: {e}")
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main()) 
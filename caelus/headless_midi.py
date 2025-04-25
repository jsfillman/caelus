#!/usr/bin/env python3
"""
Headless MIDI-to-OSC Bridge for Caelus

Simple script that:
1. Lists and connects to available MIDI ports
2. Converts MIDI messages to OSC
3. Sends OSC messages to the router
"""
import os
import sys
import time
import signal
import argparse
import threading
from typing import List, Optional

from lib.core.utils import LOG
from lib.midi_osc.midi_worker import MidiWorker
from lib.midi_osc.helpers import send_osc
from pythonosc import udp_client

# Default settings
DEFAULT_ROUTER_PORT = 9000
DEFAULT_ROUTER_IP = "127.0.0.1"
DEFAULT_ROUTER_NAME = "router"

# Keep track of workers for cleanup
midi_workers = []
running = True

def signal_handler(sig, frame):
    """Handle SIGINT (Ctrl+C) to clean up before exiting."""
    global running
    LOG.info("Shutting down...")
    running = False
    stop_all_workers()
    # Send all notes off as a safety measure
    try:
        client = udp_client.SimpleUDPClient(args.ip, args.port)
        client.send_message(f"/{args.router}/all_notes_off", [])
        LOG.info("Sent all notes off message")
    except Exception as e:
        LOG.error(f"Error sending all notes off: {e}")
    sys.exit(0)

def list_midi_ports() -> List[str]:
    """List available MIDI input ports."""
    try:
        import mido
        ports = mido.get_input_names()
        return ports
    except ImportError:
        LOG.error("Error: mido library not installed. Cannot access MIDI ports.")
        return []
    except Exception as e:
        LOG.error(f"Error listing MIDI ports: {e}")
        return []

def handle_midi(msg, osc_client, router_name):
    """
    Handle incoming MIDI messages and convert to OSC.
    
    Args:
        msg: MIDI message to process
        osc_client: OSC client to send messages
        router_name: Name of the OSC router
    """
    try:
        # Skip messages we don't care about
        if msg.type not in ['note_on', 'note_off', 'control_change', 'pitchwheel', 'aftertouch', 'polytouch']:
            return
            
        # Convert MIDI message to OSC
        if msg.type == 'note_on':
            if msg.velocity == 0:
                # Note-on with velocity 0 is same as note-off
                LOG.info(f"Note Off: {msg.note}")
                send_osc(osc_client, f"/{router_name}/note_off", [msg.note])
            else:
                # Normalize velocity to 0-1 range
                velocity = msg.velocity / 127.0
                LOG.info(f"Note On: {msg.note}, velocity={velocity:.2f}")
                send_osc(osc_client, f"/{router_name}/note_on", [msg.note, velocity])
                
        elif msg.type == 'note_off':
            LOG.info(f"Note Off: {msg.note}")
            send_osc(osc_client, f"/{router_name}/note_off", [msg.note])
            
        elif msg.type == 'control_change':
            # If CC 64 (sustain), handle specially
            if msg.control == 64:
                value = msg.value / 127.0
                LOG.info(f"Sustain: {value:.2f}")
                send_osc(osc_client, f"/{router_name}/sustain", [value])
            else:
                value = msg.value / 127.0
                LOG.info(f"CC: {msg.control}={value:.2f}")
                send_osc(osc_client, f"/{router_name}/cc", [msg.control, value])
            
        elif msg.type == 'pitchwheel':
            # Normalize to -1 to 1 range
            pitch_bend = msg.pitch / 8192.0
            LOG.info(f"Pitch Bend: {pitch_bend:.2f}")
            send_osc(osc_client, f"/{router_name}/pitch_bend", [pitch_bend])
            
        elif msg.type == 'aftertouch':
            # Normalize to 0-1 range
            pressure = msg.value / 127.0
            LOG.info(f"Aftertouch: {pressure:.2f}")
            send_osc(osc_client, f"/{router_name}/aftertouch", [pressure])
            
        elif msg.type == 'polytouch':
            # Normalize to 0-1 range
            pressure = msg.value / 127.0
            LOG.info(f"Poly Aftertouch: note={msg.note}, pressure={pressure:.2f}")
            send_osc(osc_client, f"/{router_name}/poly_aftertouch", [msg.note, pressure])
            
    except Exception as e:
        LOG.error(f"Error handling MIDI message: {e}")
        import traceback
        traceback.print_exc()

def start_midi_port(port_name, osc_client, router_name) -> Optional[MidiWorker]:
    """
    Start MIDI input from the specified port.
    
    Args:
        port_name: Name of the MIDI port to use
        osc_client: OSC client to send messages
        router_name: Name of the OSC router
        
    Returns:
        MidiWorker instance if successful, None otherwise
    """
    try:
        import mido
        # Test if we can open the port
        LOG.info(f"Testing MIDI port: {port_name}")
        test_port = mido.open_input(port_name)
        test_port.close()
        
        # Create a partial function that includes the osc_client and router_name
        def midi_callback(msg):
            handle_midi(msg, osc_client, router_name)
        
        # Create and start the worker
        worker = MidiWorker(port_name, midi_callback)
        worker.start()
        LOG.info(f"Started MIDI worker for port: {port_name}")
        return worker
    except Exception as e:
        LOG.error(f"ERROR connecting to MIDI port {port_name}: {e}")
        return None

def stop_all_workers():
    """Stop all MIDI workers."""
    global midi_workers
    LOG.info(f"Stopping {len(midi_workers)} MIDI workers...")
    for worker in midi_workers:
        try:
            worker.stop()
        except Exception:
            pass
    midi_workers = []

def main():
    """Start the headless MIDI-to-OSC bridge."""
    global running, midi_workers, args
    
    # Parse arguments
    parser = argparse.ArgumentParser(description="Headless MIDI-to-OSC Bridge for Caelus")
    parser.add_argument("--port", type=int, default=DEFAULT_ROUTER_PORT,
                      help=f"Router port (default: {DEFAULT_ROUTER_PORT})")
    parser.add_argument("--ip", type=str, default=DEFAULT_ROUTER_IP,
                      help=f"Router IP (default: {DEFAULT_ROUTER_IP})")
    parser.add_argument("--router", type=str, default=DEFAULT_ROUTER_NAME,
                      help=f"Router name (default: {DEFAULT_ROUTER_NAME})")
    parser.add_argument("--midi-port", type=str, default=None,
                      help="MIDI port to use (default: use first available)")
    parser.add_argument("--list", action="store_true",
                      help="List available MIDI ports and exit")
    
    args = parser.parse_args()
    
    # List MIDI ports if requested
    if args.list:
        ports = list_midi_ports()
        if ports:
            print("Available MIDI ports:")
            for i, port in enumerate(ports):
                print(f"  {i+1}: {port}")
        else:
            print("No MIDI ports found.")
        return 0
    
    # Register signal handler for clean shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    # List available MIDI ports
    available_ports = list_midi_ports()
    if not available_ports:
        LOG.error("No MIDI ports available. Exiting.")
        return 1
    
    LOG.info("Available MIDI ports:")
    for i, port in enumerate(available_ports):
        LOG.info(f"  {i+1}: {port}")
    
    # Create OSC client
    osc_client = udp_client.SimpleUDPClient(args.ip, args.port)
    LOG.info(f"Created OSC client for router at {args.ip}:{args.port}")
    
    # Connect to specified port or all ports
    if args.midi_port:
        # Connect to specified port
        if args.midi_port not in available_ports:
            LOG.error(f"Specified MIDI port not found: {args.midi_port}")
            LOG.info(f"Available ports: {', '.join(available_ports)}")
            return 1
        
        worker = start_midi_port(args.midi_port, osc_client, args.router)
        if worker:
            midi_workers.append(worker)
        else:
            LOG.error(f"Failed to connect to MIDI port: {args.midi_port}")
            return 1
    else:
        # Connect to first available port
        if available_ports:
            LOG.info(f"Connecting to first available MIDI port: {available_ports[0]}")
            worker = start_midi_port(available_ports[0], osc_client, args.router)
            if worker:
                midi_workers.append(worker)
            else:
                LOG.error(f"Failed to connect to MIDI port: {available_ports[0]}")
                return 1
        else:
            LOG.error("No MIDI ports available. Exiting.")
            return 1
    
    LOG.info("MIDI-to-OSC bridge running. Press Ctrl+C to stop.")
    
    try:
        # Keep the script running
        while running:
            time.sleep(0.1)
    except KeyboardInterrupt:
        LOG.info("Interrupted by user")
    finally:
        stop_all_workers()
        # Send all notes off as a safety measure
        try:
            osc_client.send_message(f"/{args.router}/all_notes_off", [])
            LOG.info("Sent all notes off message")
        except Exception as e:
            LOG.error(f"Error sending all notes off: {e}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 
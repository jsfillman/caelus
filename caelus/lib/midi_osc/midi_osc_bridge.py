"""
MIDI to OSC bridge for Caelus.

Handles the MIDI input and OSC output functionality without any GUI code.
"""
import sys
import argparse
from typing import Callable, Optional

from lib.core.utils import LOG
from lib.midi_osc.midi_worker import MidiWorker
from lib.midi_osc.helpers import send_osc
from pythonosc import udp_client

class MidiOscBridge:
    """
    Bridge between MIDI input and OSC output.
    
    Handles MIDI input from a specified port and converts it to OSC messages
    that are sent to the router.
    """
    def __init__(
        self, 
        osc_ip: str = "127.0.0.1", 
        osc_port: int = 9000, 
        router_name: str = "router",
        midi_callback: Optional[Callable] = None
    ):
        """
        Initialize the MIDI-OSC bridge.
        
        Args:
            osc_ip: IP address of the OSC router
            osc_port: Port of the OSC router
            router_name: Name of the OSC router
            midi_callback: Optional callback for MIDI messages (for monitoring)
        """
        self.osc_ip = osc_ip
        self.osc_port = osc_port
        self.router_name = router_name
        self.midi_callback = midi_callback
        
        # Create OSC client
        self.osc_client = udp_client.SimpleUDPClient(self.osc_ip, self.osc_port)
        
        # MIDI worker
        self.midi_worker = None
        self.midi_port_name = None
    
    def start_midi(self, port_name: str) -> bool:
        """
        Start MIDI input from the specified port.
        
        Args:
            port_name: Name of the MIDI port to use
            
        Returns:
            True if successful, False otherwise
        """
        if self.midi_worker:
            self.stop_midi()
        
        try:
            import mido
            # Test if we can open the port
            LOG.info(f"Testing MIDI port: {port_name}")
            test_port = mido.open_input(port_name)
            test_port.close()
            
            # Create the worker
            self.midi_worker = MidiWorker(port_name, self.handle_midi)
            self.midi_worker.start()
            self.midi_port_name = port_name
            LOG.info(f"Started MIDI worker for port: {port_name}")
            return True
        except Exception as e:
            LOG.error(f"ERROR connecting to MIDI port: {e}")
            return False
    
    def stop_midi(self) -> None:
        """Stop MIDI input."""
        if self.midi_worker:
            self.midi_worker.stop()
            self.midi_worker = None
            LOG.info("Stopped MIDI worker")
    
    def handle_midi(self, msg) -> None:
        """
        Handle incoming MIDI messages.
        
        Args:
            msg: MIDI message to process
        """
        try:
            # Skip messages we don't care about
            if msg.type not in ['note_on', 'note_off', 'control_change', 'pitchwheel', 'aftertouch', 'polytouch']:
                return
                
            LOG.debug(f"MIDI: {msg}")
            
            # Call the callback if provided
            if self.midi_callback:
                self.midi_callback(msg)
            
            # Convert MIDI message to OSC
            if msg.type == 'note_on':
                if msg.velocity == 0:
                    # Note-on with velocity 0 is same as note-off
                    send_osc(self.osc_client, f"/{self.router_name}/note_off", [msg.note])
                else:
                    # Normalize velocity to 0-1 range
                    velocity = msg.velocity / 127.0
                    send_osc(self.osc_client, f"/{self.router_name}/note_on", [msg.note, velocity])
                    
            elif msg.type == 'note_off':
                send_osc(self.osc_client, f"/{self.router_name}/note_off", [msg.note])
                
            elif msg.type == 'control_change':
                # If CC 64 (sustain), handle specially
                if msg.control == 64:
                    send_osc(self.osc_client, f"/{self.router_name}/sustain", [msg.value])
                else:
                    send_osc(self.osc_client, f"/{self.router_name}/cc", [msg.control, msg.value])
                
            elif msg.type == 'pitchwheel':
                # Normalize to -1 to 1 range
                pitch_bend = msg.pitch / 8192.0
                send_osc(self.osc_client, f"/{self.router_name}/pitch_bend", [pitch_bend])
                
            elif msg.type == 'aftertouch':
                # Normalize to 0-1 range
                pressure = msg.value / 127.0
                send_osc(self.osc_client, f"/{self.router_name}/aftertouch", [pressure])
                
            elif msg.type == 'polytouch':
                # Normalize to 0-1 range
                pressure = msg.value / 127.0
                send_osc(self.osc_client, f"/{self.router_name}/poly_aftertouch", [msg.note, pressure])
                
        except Exception as e:
            LOG.error(f"Error handling MIDI message: {e}")
            import traceback
            traceback.print_exc()
    
    def send_panic(self) -> bool:
        """
        Send all notes off message.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            send_osc(self.osc_client, f"/{self.router_name}/all_notes_off", [])
            LOG.info("Sent all notes off message")
            return True
        except Exception as e:
            LOG.error(f"Error sending all notes off: {e}")
            return False
    
    def list_midi_ports(self) -> list:
        """
        Get a list of available MIDI input ports.
        
        Returns:
            List of MIDI port names
        """
        try:
            import mido
            return mido.get_input_names()
        except Exception as e:
            LOG.error(f"Error getting MIDI ports: {e}")
            return []


# Standalone usage
def main() -> int:
    """
    Run the MIDI-OSC bridge from the command line.
    
    Returns:
        Exit code
    """
    parser = argparse.ArgumentParser(description="MIDI to OSC bridge for Caelus")
    parser.add_argument("--port", type=int, default=9000, help="Router's OSC port")
    parser.add_argument("--ip", type=str, default="127.0.0.1", help="Router's IP address")
    parser.add_argument("--router", type=str, default="router", help="OSC router name")
    
    args = parser.parse_args()
    
    # Create bridge
    bridge = MidiOscBridge(
        osc_ip=args.ip,
        osc_port=args.port,
        router_name=args.router
    )
    
    # List available MIDI ports
    ports = bridge.list_midi_ports()
    if not ports:
        LOG.error("No MIDI ports found. Please connect a MIDI device and try again.")
        return 1
    
    # Print available ports
    LOG.info("Available MIDI ports:")
    for i, port in enumerate(ports):
        LOG.info(f"  {i+1}: {port}")
    
    # Ask user to select a port
    try:
        selection = int(input("Select MIDI port (number): "))
        if 1 <= selection <= len(ports):
            selected_port = ports[selection-1]
            LOG.info(f"Selected port: {selected_port}")
            
            # Start MIDI input
            if bridge.start_midi(selected_port):
                LOG.info("MIDI-OSC bridge started. Press Ctrl+C to stop.")
                
                # Wait for Ctrl+C
                try:
                    while True:
                        import time
                        time.sleep(1)
                except KeyboardInterrupt:
                    LOG.info("Stopping MIDI-OSC bridge")
                    bridge.stop_midi()
            else:
                LOG.error("Failed to start MIDI input")
                return 1
        else:
            LOG.error("Invalid selection")
            return 1
    except (ValueError, KeyboardInterrupt):
        LOG.info("Exiting")
        return 0
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 
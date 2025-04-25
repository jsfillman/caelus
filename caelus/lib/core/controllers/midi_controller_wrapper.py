"""
MIDI controller wrapper for Caelus.

This module provides a wrapper around the MidiController for handling MIDI to OSC conversion.
"""
from typing import Optional, Callable, Dict, List, Any
import time

from PyQt6.QtCore import QObject
from pythonosc import udp_client

from lib.core.utils import LOG
from lib.midi_osc.midi_controller import MidiController
from lib.midi_osc.midi_worker import MidiWorker
from lib.midi_osc.helpers import send_osc
from lib.ui.signals.signal_handlers import UISignalHandler

class MidiControllerWrapper(QObject):
    """
    Wrapper for the MidiController that handles MIDI to OSC conversion.
    
    Responsibilities:
    - Manage MIDI port connection/disconnection
    - Convert MIDI messages to OSC messages
    - Send OSC messages to the router
    - Update UI based on MIDI activity
    """
    
    def __init__(
        self,
        osc_client: udp_client.SimpleUDPClient, 
        router_name: str = "router",
        ui_signal_handler: Optional[UISignalHandler] = None
    ):
        """
        Initialize the MIDI controller wrapper.
        
        Args:
            osc_client: OSC client for sending OSC messages
            router_name: Name of the OSC router
            ui_signal_handler: Signal handler for updating UI
        """
        super().__init__()
        
        # Store parameters
        self.osc_client = osc_client
        self.router_name = router_name
        self.ui_signal_handler = ui_signal_handler
        
        # Create MidiController instance
        self.midi_ctrl = MidiController()
        
        # Connect signals if UI signal handler is provided
        if ui_signal_handler:
            self.midi_ctrl.midi_light_update.connect(self._update_midi_light)
            self.midi_ctrl.midi_event.connect(self.handle_midi)
        
        # Current MIDI worker (for active port)
        self.worker: Optional[MidiWorker] = None
    
    def list_ports(self) -> List[str]:
        """
        List available MIDI input ports.
        
        Returns:
            List of available MIDI port names
        """
        return self.midi_ctrl.list_ports()
    
    def select_port(self, port_name: str) -> bool:
        """
        Select and connect to a MIDI port.
        
        Args:
            port_name: Name of the MIDI port to connect to
            
        Returns:
            True if connection successful, False otherwise
        """
        # Stop existing worker if any
        if self.worker:
            self.worker.stop()
            self.worker = None
            LOG.info("Stopped existing MIDI worker")
        
        if "No MIDI ports found" in port_name or "Error" in port_name:
            LOG.warning("Cannot connect to invalid MIDI port")
            return False
        
        try:
            import mido
            # Test if we can open the port
            LOG.info(f"Testing MIDI port: {port_name}")
            test_port = mido.open_input(port_name)
            test_port.close()
            LOG.info("MIDI port test successful")
            
            # Create and start worker
            self.worker = MidiWorker(port_name, self.handle_midi)
            self.worker.start()
            LOG.info(f"Started MIDI worker for port: {port_name}")
            return True
            
        except Exception as e:
            LOG.error(f"ERROR connecting to MIDI port: {e}")
            return False
    
    def handle_midi(self, msg) -> None:
        """
        Handle incoming MIDI messages and convert to OSC.
        
        Args:
            msg: MIDI message object
        """
        try:
            # Signal UI to update MIDI light if handler is available
            if self.ui_signal_handler:
                self.ui_signal_handler.midi_light_update.emit(True)
            
            # Skip messages we don't care about
            if msg.type not in ['note_on', 'note_off', 'control_change', 
                               'pitchwheel', 'aftertouch', 'polytouch']:
                return
            
            # LOG.debug(f"MIDI: {msg}")
            
            # Convert MIDI message to OSC based on type
            self._convert_and_send_osc(msg)
            
            # Signal UI to update OSC light if handler is available
            if self.ui_signal_handler:
                self.ui_signal_handler.osc_light_update.emit(True)
                
        except Exception as e:
            LOG.error(f"Error handling MIDI message: {e}")
            import traceback
            traceback.print_exc()
    
    def _convert_and_send_osc(self, msg) -> None:
        """
        Convert MIDI message to OSC and send it to the router.
        
        Args:
            msg: MIDI message object
        """
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
    
    def _update_midi_light(self, on: bool) -> None:
        """
        Handle MIDI light update signal from MidiController.
        
        Args:
            on: Whether the light should be on
        """
        if self.ui_signal_handler:
            self.ui_signal_handler.midi_light_update.emit(on)
    
    def panic(self) -> None:
        """Send all notes off message to the router."""
        try:
            send_osc(self.osc_client, f"/{self.router_name}/all_notes_off", [])
            LOG.info("PANIC - sending all notes off")
        except Exception as e:
            LOG.error(f"Error sending panic message: {e}")
    
    def stop(self) -> None:
        """Stop the MIDI controller and worker."""
        # Stop MIDI controller
        if self.midi_ctrl:
            self.midi_ctrl.stop()
        
        # Stop worker if any
        if self.worker:
            self.worker.stop()
            self.worker = None
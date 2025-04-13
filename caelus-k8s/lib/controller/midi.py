#!/usr/bin/env python3
"""
MIDI input module for Caelus K8s controller.
"""

import logging
import threading
import time
import mido
from mido import Message

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MIDIInputHandler:
    """MIDI input handler using mido."""
    
    def __init__(self, callback=None):
        """Initialize MIDI input handler.
        
        Args:
            callback (callable, optional): Callback function for MIDI messages
        """
        self.callback = callback
        self.port = None
        self.running = False
        self.thread = None
        
        # Get available input ports
        self.available_ports = mido.get_input_names()
        logger.info(f"Available MIDI input ports: {self.available_ports}")
    
    def set_callback(self, callback):
        """Set callback function for MIDI messages.
        
        Args:
            callback (callable): Callback function
        """
        self.callback = callback
    
    def open_port(self, port_name=None):
        """Open a MIDI input port.
        
        Args:
            port_name (str, optional): Name of the port to open. If None, open the first available port.
            
        Returns:
            bool: True if port was opened successfully, False otherwise
        """
        # Close any open ports
        self.close_port()
        
        try:
            if port_name is None:
                if self.available_ports:
                    port_name = self.available_ports[0]
                else:
                    logger.error("No MIDI input ports available")
                    return False
            
            self.port = mido.open_input(port_name, callback=self._message_callback)
            logger.info(f"Opened MIDI input port: {port_name}")
            return True
        except Exception as e:
            logger.error(f"Error opening MIDI input port: {e}")
            return False
    
    def open_virtual_port(self, port_name="Caelus MIDI In"):
        """Open a virtual MIDI input port.
        
        Args:
            port_name (str, optional): Name of the virtual port
            
        Returns:
            bool: True if port was opened successfully, False otherwise
        """
        # Close any open ports
        self.close_port()
        
        try:
            self.port = mido.open_input(port_name, virtual=True, callback=self._message_callback)
            logger.info(f"Opened virtual MIDI input port: {port_name}")
            return True
        except Exception as e:
            logger.error(f"Error opening virtual MIDI input port: {e}")
            return False
    
    def close_port(self):
        """Close the MIDI input port."""
        if self.port is not None:
            self.port.close()
            self.port = None
            logger.info("Closed MIDI input port")
    
    def _message_callback(self, message):
        """Process MIDI messages.
        
        Args:
            message (mido.Message): MIDI message
        """
        if self.callback is not None:
            self.callback(message)
        else:
            # Default message handling
            if message.type == 'note_on':
                logger.info(f"Note On: {message.note}, Velocity: {message.velocity}")
            elif message.type == 'note_off':
                logger.info(f"Note Off: {message.note}")
            else:
                logger.debug(f"MIDI message: {message}")
    
    def send_test_notes(self, notes=[60, 64, 67, 71], velocity=100, duration=0.5):
        """Send test MIDI notes.
        
        Args:
            notes (list): List of MIDI note numbers
            velocity (int): MIDI velocity (0-127)
            duration (float): Note duration in seconds
        """
        for note in notes:
            # Note on
            note_on = Message('note_on', note=note, velocity=velocity)
            self._message_callback(note_on)
            
            # Wait for duration
            time.sleep(duration)
            
            # Note off
            note_off = Message('note_off', note=note, velocity=0)
            self._message_callback(note_off)
            
            # Small gap between notes
            time.sleep(0.1)
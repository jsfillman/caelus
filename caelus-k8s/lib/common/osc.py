#!/usr/bin/env python3
"""
Common OSC utilities for Caelus K8s.
"""

import logging
from pythonosc import udp_client, dispatcher, osc_server
import threading

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# OSC message types
NOTE_ON = "/caelus/note/on"
NOTE_OFF = "/caelus/note/off"
AFTERTOUCH_POLY = "/caelus/aftertouch/poly"
AFTERTOUCH_CHANNEL = "/caelus/aftertouch/channel"
WORKER_READY = "/caelus/worker/ready"
WORKER_STATUS = "/caelus/worker/status"

class OSCClient:
    """Simple OSC client for sending messages to workers."""
    
    def __init__(self, ip, port):
        """Initialize OSC client.
        
        Args:
            ip (str): IP address of the OSC server
            port (int): Port of the OSC server
        """
        self.ip = ip
        self.port = port
        self.client = udp_client.SimpleUDPClient(ip, port)
        logger.info(f"OSC client initialized for {ip}:{port}")
        
    def send_note_on(self, note, velocity, rtp_port=None):
        """Send note on message.
        
        Args:
            note (int): MIDI note number (0-127)
            velocity (int): MIDI velocity (0-127)
            rtp_port (int, optional): RTP port to stream audio back to
        """
        if rtp_port:
            self.client.send_message(NOTE_ON, [note, velocity, rtp_port])
            logger.debug(f"Sent note on: {note}, {velocity}, {rtp_port}")
        else:
            self.client.send_message(NOTE_ON, [note, velocity])
            logger.debug(f"Sent note on: {note}, {velocity}")
        
    def send_note_off(self, note):
        """Send note off message.
        
        Args:
            note (int): MIDI note number (0-127)
        """
        self.client.send_message(NOTE_OFF, [note])
        logger.debug(f"Sent note off: {note}")
        
    def send_aftertouch_poly(self, note, pressure):
        """Send polyphonic aftertouch message.
        
        Args:
            note (int): MIDI note number (0-127)
            pressure (int): Aftertouch pressure value (0-127)
        """
        self.client.send_message(AFTERTOUCH_POLY, [note, pressure])
        logger.debug(f"Sent poly aftertouch: note={note}, pressure={pressure}")
        
    def send_aftertouch_channel(self, pressure):
        """Send channel aftertouch message.
        
        Args:
            pressure (int): Aftertouch pressure value (0-127)
        """
        self.client.send_message(AFTERTOUCH_CHANNEL, [pressure])
        logger.debug(f"Sent channel aftertouch: pressure={pressure}")

class OSCServer:
    """Simple OSC server for receiving messages from controller/workers."""
    
    def __init__(self, ip, port, dispatcher=None):
        """Initialize OSC server.
        
        Args:
            ip (str): IP address to listen on
            port (int): Port to listen on
            dispatcher (Dispatcher, optional): OSC message dispatcher
        """
        self.ip = ip
        self.port = port
        
        if dispatcher is None:
            self.dispatcher = self._create_default_dispatcher()
        else:
            self.dispatcher = dispatcher
            
        # Server will be initialized in the start method
        self.server = None
        self.server_thread = None
        logger.info(f"OSC server initialized for {ip}:{port}")
        
    def _create_default_dispatcher(self):
        """Create a default dispatcher with basic handlers."""
        disp = dispatcher.Dispatcher()
        disp.map(WORKER_READY, self._on_worker_ready)
        disp.map(WORKER_STATUS, self._on_worker_status)
        return disp
    
    def _on_worker_ready(self, address, *args):
        """Default handler for worker ready messages."""
        logger.info(f"Worker ready: {args}")
    
    def _on_worker_status(self, address, *args):
        """Default handler for worker status messages."""
        logger.info(f"Worker status: {args}")
    
    def add_handler(self, address, handler):
        """Add a message handler.
        
        Args:
            address (str): OSC address pattern
            handler (callable): Handler function
        """
        self.dispatcher.map(address, handler)
        logger.debug(f"Added handler for {address}")
    
    def start(self):
        """Start the OSC server in a background thread."""
        if self.server is not None:
            logger.warning("OSC server already running")
            return
            
        self.server = osc_server.ThreadingOSCUDPServer(
            (self.ip, self.port), self.dispatcher)
        
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()
        logger.info(f"OSC server started on {self.ip}:{self.port}")
    
    def stop(self):
        """Stop the OSC server."""
        if self.server is None:
            logger.warning("OSC server not running")
            return
            
        self.server.shutdown()
        self.server = None
        self.server_thread = None
        logger.info("OSC server stopped")
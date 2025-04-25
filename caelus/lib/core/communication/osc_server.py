"""
OSC server for Caelus.

This module provides a thread-safe OSC server for handling OSC messages from MIDI bridge.
"""
import os
import time
import threading
from typing import Callable, Dict, List, Optional, Any, Tuple

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer

from lib.common.utils import LOG
from ui.signals.signal_handlers import OSCSignalHandler

class OSCServerThread(threading.Thread):
    """
    Thread to run OSC server in background.
    
    Listens for messages from the router and forwards them to the GUI.
    """
    
    def __init__(
        self, 
        signal_handler: OSCSignalHandler, 
        listen_port: int = 9002
    ):
        """
        Initialize the OSC server thread.
        
        Args:
            signal_handler: Handler to emit signals to the GUI
            listen_port: Port to listen on for OSC messages
        """
        super().__init__(daemon=True)
        
        # Store parameters
        self.signal_handler = signal_handler
        self.listen_port = listen_port
        
        # Create dispatcher and server
        self.dispatcher = Dispatcher()
        self.running = True
        self.server: Optional[ThreadingOSCUDPServer] = None
        
        # Set up OSC message handlers
        self._setup_handlers()
    
    def _setup_handlers(self) -> None:
        """Set up OSC message handlers for different address patterns."""
        # Status message handler
        self.dispatcher.map("/ui/status", self._handle_status)
        
        # Parameter update handler
        self.dispatcher.map("/ui/param", self._handle_param_update)
        
        # Wildcard handler for debugging
        self.dispatcher.map("/*", self._handle_wildcard)
    
    def _handle_status(self, address: str, *args: Any) -> None:
        """
        Handle status messages from router.
        
        Args:
            address: OSC address pattern
            *args: OSC arguments (status_type, message)
        """
        LOG.info(f"Received status OSC message: {address} {args}")
        
        if len(args) >= 2:
            status_type = str(args[0])
            message = str(args[1])
            LOG.info(f"Received status: {status_type} - {message}")
            
            # Emit signal for GUI to update
            self.signal_handler.status_updated.emit(status_type, message)
    
    def _handle_param_update(self, address: str, *args: Any) -> None:
        """
        Handle parameter updates from router.
        
        Args:
            address: OSC address pattern
            *args: OSC arguments (param_name, value)
        """
        LOG.info(f"Received param OSC message: {address} {args}")
        
        if len(args) >= 2:
            param_name = str(args[0])
            value = float(args[1])
            LOG.info(f"Parameter update: {param_name} = {value}")
            
            # Emit signal for GUI to update
            self.signal_handler.param_changed.emit(param_name, value)
    
    def _handle_wildcard(self, address: str, *args: Any) -> None:
        """
        Debug handler for all OSC messages.
        
        Args:
            address: OSC address pattern
            *args: OSC arguments
        """
        # Only log messages that aren't handled by dedicated handlers
        if not (address.startswith('/ui/status') or address.startswith('/ui/param')):
            LOG.info(f"Received wildcard OSC message: {address} {args}")
            LOG.debug(f"Received unhandled OSC: {address} {args}")
    
    def run(self) -> None:
        """Run the OSC server in a separate thread."""
        try:
            # Create server
            self.server = ThreadingOSCUDPServer(
                ("127.0.0.1", self.listen_port), 
                self.dispatcher
            )
            LOG.info(f"OSC server listening on 127.0.0.1:{self.listen_port}")
            
            # Modified serve_forever loop that can be stopped
            count = 0
            last_log = time.time()
            
            try:
                while self.running:
                    # Handle any incoming message
                    try:
                        self.server.handle_request()
                    except Exception as e:
                        LOG.error(f"Error handling OSC request: {e}")
                    
                    # Log a heartbeat message occasionally
                    count += 1
                    if count % 100 == 0 or time.time() - last_log > 10:
                        LOG.info(f"OSC server still listening on 127.0.0.1:{self.listen_port}...")
                        last_log = time.time()
            except KeyboardInterrupt:
                LOG.info("OSC server stopped by keyboard interrupt")
                self.running = False
                
        except Exception as e:
            LOG.error(f"Error in OSC server: {e}")
            import traceback
            traceback.print_exc()
    
    def stop(self) -> None:
        """Stop the OSC server thread."""
        self.running = False
        
        if self.server:
            # Close the socket
            self.server.socket.close()
            
        LOG.info("OSC server stopped")
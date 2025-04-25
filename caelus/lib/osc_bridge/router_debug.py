"""
Debugging version of OSC Router Module

This is a patched version of router.py with additional debug logging
to help diagnose issues with voice allocation and OSC message routing.
"""
import sys
import os
import logging
from typing import Dict, List, Optional, Any, Tuple

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer
from pythonosc import udp_client

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, parent_dir)

from lib.core.utils import LOG, DEFAULT_ROUTER_PORT, DEFAULT_SYNTH_HOST, DEFAULT_SYNTH_NAME
from lib.osc_bridge.voice import Voice
from lib.osc_bridge.voice_manager import VoiceManager
from lib.osc_bridge.config_loader import ConfigLoader
from lib.osc_bridge.ui_bridge import UIBridge
from lib.osc_bridge.variable_manager import VariableManager

# Set up enhanced logging
LOG.setLevel(logging.DEBUG)
# Add a stream handler if there isn't one already
if not LOG.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    LOG.addHandler(handler)

class OSCRouterDebug:
    """
    Debugging version of the OSC Router.
    This class has the same functionality as OSCRouter, but with extra debug logging.
    """
    
    def __init__(
        self, 
        config_file: Optional[str] = None, 
        router_port: int = DEFAULT_ROUTER_PORT,
        ui_host: Optional[str] = None, 
        ui_port: Optional[int] = None
    ) -> None:
        """
        Initialize the OSC router with config.
        
        Args:
            config_file: Path to configuration file (YAML or JSON)
            router_port: Port to listen on for incoming OSC messages
            ui_host: Host for sending UI feedback
            ui_port: Port for sending UI feedback
        """
        # Store the router port
        self.router_port: int = router_port
        
        # UI communication client - handles bidirectional UI comms
        self.ui_bridge: UIBridge = UIBridge()
        
        # Setup UI client if host and port provided (outbound channel)
        if ui_host and ui_port:
            self.ui_bridge.setup_client(ui_host, ui_port)
        
        # Default synth values
        self.synth_name: str = DEFAULT_SYNTH_NAME
        self.synth_host: str = DEFAULT_SYNTH_HOST
        
        # Initialize variable manager
        self.variable_manager: VariableManager = VariableManager(self)
        
        # Initialize voice manager with empty list (will populate after loading config)
        self.voice_manager: VoiceManager = VoiceManager([])
        
        # Create OSC dispatcher for handling INBOUND messages
        self.dispatcher: Dispatcher = Dispatcher()
        
        # Register OSC handlers via controller classes
        from lib.osc_bridge.controllers import CONTROLLERS
        for controller in CONTROLLERS:
            controller(self, self.dispatcher)
        
        # Load config if provided
        if config_file:
            self.load_config(config_file)
        
        # Initialize server that will listen for INBOUND messages
        self.server: Optional[ThreadingOSCUDPServer] = None
        
        # Extra debug logging
        LOG.debug(f"Initialized OSCRouterDebug with router_port={router_port}")
        LOG.debug(f"Default synth_name={self.synth_name}, synth_host={self.synth_host}")
        LOG.debug(f"UI bridge: ui_host={ui_host}, ui_port={ui_port}")
    
    def load_config(self, config_file: str) -> bool:
        """
        Load configuration from file.
        
        Args:
            config_file: Path to configuration file
            
        Returns:
            True if loading was successful
        """
        try:
            # Load configuration
            settings, voices = ConfigLoader.load_config(config_file)
            
            # Store settings
            self.synth_name = settings['synth_name']
            self.synth_host = settings['synth_host']
            
            LOG.info(f"Using default synth '{self.synth_name}' on default host '{self.synth_host}'")
            
            # Print detailed info about each voice
            LOG.debug(f"Loaded {len(voices)} voices from config:")
            for i, voice in enumerate(voices):
                LOG.debug(f"Voice {i}: id={voice.id}, port={voice.port}, host={voice.host}, synth_name={voice.synth_name}")
            
            # Create new voice manager with the loaded voices
            self.voice_manager = VoiceManager(voices)
            
            LOG.info(f"Loaded configuration from {config_file}")
            LOG.info(f"Configured {len(voices)} voices")
            
            # Notify UI if connected
            self.send_ui_status("info", f"Loaded {len(voices)} voices from config")
                
            return True
        except Exception as e:
            LOG.error(f"Error loading config: {e}")
            import traceback
            LOG.error(f"Stack trace: {traceback.format_exc()}")
            
            if self.ui_bridge.ui_client:
                self.send_ui_status("error", f"Failed to load config: {str(e)}")
            return False
    
    def handle_note_on(self, address: str, *args: Any) -> None:
        """
        Handle note on messages from MIDI-OSC bridge.
        
        Args:
            address: OSC address
            *args: OSC arguments (note, velocity)
        """
        if len(args) < 2:
            LOG.warning(f"Invalid note_on message: {args}")
            return
        
        # Extract note number and velocity
        note_num = int(args[0])
        velocity = float(args[1])
        
        LOG.debug(f"ROUTER DEBUG: Received note_on: {note_num}, {velocity}")
        
        # Debug voice manager state before processing
        active_notes_before = self.voice_manager.active_notes.copy() if hasattr(self.voice_manager, 'active_notes') else {}
        LOG.debug(f"ROUTER DEBUG: Before note_on, active_notes={active_notes_before}")
        
        # Process through voice manager
        result = self.voice_manager.note_on(note_num, velocity)
        
        # Debug voice manager state after processing
        active_notes_after = self.voice_manager.active_notes.copy() if hasattr(self.voice_manager, 'active_notes') else {}
        LOG.debug(f"ROUTER DEBUG: After note_on, active_notes={active_notes_after}")
        LOG.debug(f"ROUTER DEBUG: note_on result: {result}")
        
        # Debug voice objects
        LOG.debug(f"ROUTER DEBUG: Voice manager has {len(self.voice_manager.voices)} voices")
        for i, voice in enumerate(self.voice_manager.voices):
            LOG.debug(f"ROUTER DEBUG: Voice {i}: id={voice.id}, port={voice.port}, active={voice.is_active}, note={voice.note}")
    
    def handle_note_off(self, address: str, *args: Any) -> None:
        """
        Handle note off messages from MIDI-OSC bridge.
        
        Args:
            address: OSC address
            *args: OSC arguments (note)
        """
        if len(args) < 1:
            LOG.warning(f"Invalid note_off message: {args}")
            return
        
        note = int(args[0])
        LOG.debug(f"ROUTER DEBUG: Received note_off: {note}")
        
        # Debug voice manager state before processing
        active_notes_before = self.voice_manager.active_notes.copy() if hasattr(self.voice_manager, 'active_notes') else {}
        LOG.debug(f"ROUTER DEBUG: Before note_off, active_notes={active_notes_before}")
        
        self.voice_manager.note_off(note)
        
        # Debug voice manager state after processing
        active_notes_after = self.voice_manager.active_notes.copy() if hasattr(self.voice_manager, 'active_notes') else {}
        LOG.debug(f"ROUTER DEBUG: After note_off, active_notes={active_notes_after}")
        
        # Send to UI
        self.send_ui_status("note", f"Note Off: {note}")
        
        # Debug voice objects
        LOG.debug(f"ROUTER DEBUG: Voice manager has {len(self.voice_manager.voices)} voices")
        for i, voice in enumerate(self.voice_manager.voices):
            LOG.debug(f"ROUTER DEBUG: Voice {i}: id={voice.id}, port={voice.port}, active={voice.is_active}, note={voice.note}")
    
    # Add the rest of the OSCRouter methods here...
    # For simplicity, I'm only including the most relevant methods for debugging
    # the voice allocation issue.
    
    def create_default_voices(self, num_voices: int = 4, start_port: int = 5510) -> bool:
        """
        Create default voices if no config is provided.
        
        Args:
            num_voices: Number of voices to create
            start_port: Starting port for voice allocation
            
        Returns:
            True if voices were created successfully
        """
        voices = []
        for i in range(num_voices):
            voice_id = i
            port = start_port + (i * 100)  # Use the increment by 100 as per design
            voice = Voice(voice_id, port, host=self.synth_host, synth_name=self.synth_name)
            voices.append(voice)
            LOG.info(f"Created default voice {i} on host {self.synth_host}, port {port}")
            LOG.debug(f"ROUTER DEBUG: Created voice: id={voice.id}, port={voice.port}, host={voice.host}, synth_name={voice.synth_name}")
        
        # Replace the voice manager
        self.voice_manager = VoiceManager(voices)
        
        # Initialize controllers for all voices (now that voice manager exists)
        self.voice_manager.reset_all_controllers()
        
        # Send to UI
        if self.ui_bridge.ui_client:
            self.send_ui_status("info", f"Created {num_voices} default voices")
        
        return True
    
    # Required methods from original router
    def setup_ui_client(self, host: str, port: int) -> bool:
        return self.ui_bridge.setup_client(host, port)
    
    def send_ui_status(self, status_type: str, message: str) -> bool:
        return self.ui_bridge.send_status(status_type, message)
    
    def send_ui_param(self, param_name: str, value: Any) -> bool:
        return self.ui_bridge.send_param(param_name, value)
    
    def start_in_background(self) -> None:
        """
        Start the OSC router in a background thread.
        
        This allows the router to run asynchronously without blocking the
        main application thread.
        """
        import threading
        
        # Initialize server object
        self.server = None
        
        # Flag to indicate if the server should keep running
        self.running = True
        
        # Create and start background thread
        self.server_thread = threading.Thread(target=self._run_in_thread, daemon=True)
        self.server_thread.start()
        LOG.info(f"OSC Router started in background thread on port {self.router_port}")
        
    def _run_in_thread(self) -> None:
        """Internal method to run the server in a background thread."""
        try:
            # Create and start OSC server for INBOUND messages
            self.server = ThreadingOSCUDPServer(("0.0.0.0", self.router_port), self.dispatcher)
            LOG.info(f"OSC Router listening on 0.0.0.0:{self.router_port}")
            LOG.info(f"Routing to {len(self.voice_manager.voices)} synth voices")
            
            # Print voice details
            for i, voice in enumerate(self.voice_manager.voices):
                LOG.info(f"Voice {i}: {voice.id} on {voice.host}:{voice.port}")
            
            # Custom serve forever that can be stopped
            while self.running:
                self.server.handle_request()
                
        except Exception as e:
            LOG.error(f"Error in router thread: {e}")
            
            # Send to UI (OUTBOUND)
            if self.ui_bridge.ui_client:
                self.send_ui_status("error", f"Router thread error: {str(e)}")

def main():
    """Simple test main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Debug OSC Router")
    parser.add_argument("config_file", help="Path to voice configuration file")
    parser.add_argument("--port", type=int, default=9000, help="Router port (default: 9000)")
    
    args = parser.parse_args()
    
    router = OSCRouterDebug(args.config_file, args.port)
    
    try:
        LOG.info(f"Starting debug router with config: {args.config_file}")
        router.start_in_background()
        
        # Keep the main thread alive
        while True:
            import time
            time.sleep(1)
            
    except KeyboardInterrupt:
        LOG.info("Stopping router...")
        router.running = False

if __name__ == "__main__":
    main()
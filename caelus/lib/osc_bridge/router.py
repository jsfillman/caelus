"""
OSC Router Module - Handles OSC message routing to synth voices.

This module provides classes for routing OSC messages to multiple synth voices:
- ConfigLoader: Handles loading configuration from files
- UIBridge: Manages bidirectional UI communication
- VariableManager: Handles getting/setting router variables
- OSCRouter: Main router class that ties everything together
"""
from typing import Dict, List, Optional, Any, Tuple

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer
from pythonosc import udp_client

from lib.common.utils import LOG, DEFAULT_ROUTER_PORT, DEFAULT_SYNTH_HOST, DEFAULT_SYNTH_NAME
from lib.osc_bridge.voice import Voice
from lib.osc_bridge.voice_manager import VoiceManager
from lib.osc_bridge.config_loader import ConfigLoader
from lib.osc_bridge.ui_bridge import UIBridge
from lib.osc_bridge.variable_manager import VariableManager


class OSCRouter:
    """
    Routes OSC messages to multiple synth voice instances.
    
    This class handles both:
    1. INBOUND: Receiving OSC messages from MIDI bridge and UIs
    2. OUTBOUND: Sending OSC messages to synth voices and UIs
    
    It's the Grand Central Station of your MIDI/OSC ecosystem -
    connections in all directions, with trains constantly arriving
    and departing on schedule.
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
    
    def setup_ui_client(self, host: str, port: int) -> bool:
        """
        Set up OSC client for sending messages to the UI.
        
        Args:
            host: UI host address
            port: UI port number
            
        Returns:
            True if setup was successful
        """
        return self.ui_bridge.setup_client(host, port)
    
    def send_ui_status(self, status_type: str, message: str) -> bool:
        """
        Send status message to UI.
        
        Args:
            status_type: Type of status (info, warning, error)
            message: Status message
            
        Returns:
            True if message was sent successfully
        """
        return self.ui_bridge.send_status(status_type, message)
    
    def send_ui_param(self, param_name: str, value: Any) -> bool:
        """
        Send parameter update to UI.
        
        Args:
            param_name: Parameter name
            value: Parameter value
            
        Returns:
            True if message was sent successfully
        """
        return self.ui_bridge.send_param(param_name, value)
    
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
            
            # Create new voice manager with the loaded voices
            self.voice_manager = VoiceManager(voices)
            
            LOG.info(f"Loaded configuration from {config_file}")
            LOG.info(f"Configured {len(voices)} voices")
            
            # Notify UI if connected
            self.send_ui_status("info", f"Loaded {len(voices)} voices from config")
                
            return True
        except Exception as e:
            LOG.error(f"Error loading config: {e}")
            if self.ui_bridge.ui_client:
                self.send_ui_status("error", f"Failed to load config: {str(e)}")
            return False
    
    def handle_register_ui(self, address: str, *args: Any) -> None:
        """
        Handle UI client registration (INBOUND message).
        
        This is how UIs establish an INBOUND channel to the router.
        The UI sends its host:port information so we can talk back to it.
        
        Flow: UI → Router (registration) → Router ↔ UI (bidirectional after setup)
        
        Args:
            address: OSC address
            *args: OSC arguments (host, port)
        """
        if len(args) < 2:
            LOG.warning(f"Invalid UI registration: {args}")
            return
            
        host = str(args[0])
        port = int(args[1])
        
        LOG.info(f"Registering UI client at {host}:{port}")
        self.setup_ui_client(host, port)
        
        # Send current state to UI (OUTBOUND)
        self.send_ui_status("info", f"Router active with {len(self.voice_manager.voices)} voices")
    
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
        
        # Process through voice manager
        self.voice_manager.note_on(note_num, velocity)
    
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
        self.voice_manager.note_off(note)
        
        # Send to UI
        self.send_ui_status("note", f"Note Off: {note}")
    
    def handle_sustain(self, address: str, *args: Any) -> None:
        """
        Handle sustain pedal messages.
        
        Args:
            address: OSC address
            *args: OSC arguments (sustain_value)
        """
        if len(args) < 1:
            LOG.warning(f"Invalid sustain message: {args}")
            return
        
        sustain_value = float(args[0])
        self.voice_manager.set_sustain(sustain_value)
        LOG.info(f"Sustain pedal changed: {sustain_value}")
        
        # Send to UI
        if sustain_value > 0.5:
            self.send_ui_status("info", "Sustain: ON")
            self.send_ui_param("sustain", 1.0)
        else:
            self.send_ui_status("info", "Sustain: OFF")
            self.send_ui_param("sustain", 0.0)
    
    def handle_cc(self, address: str, *args: Any) -> None:
        """
        Handle CC messages.
        
        Args:
            address: OSC address
            *args: OSC arguments (cc_num, value)
        """
        if len(args) < 2:
            LOG.warning(f"Invalid CC message: {args}")
            return
        
        cc_num = int(args[0])
        value = float(args[1])
        
        LOG.info(f"Router received CC: {cc_num}={value}")
        
        # Value normalization - MIDI typically sends 0-127
        if cc_num == 64:  # Sustain pedal
            # Send directly to sustain handler
            LOG.info(f"Routing sustain pedal CC: {cc_num}={value}")
            self.handle_sustain(address, value)
        else:
            # For other CCs (including modulation wheel and expression)
            # Ensure value is between 0-1 for filter cutoff calculations
            normalized_value = value
            if value > 1.0:
                normalized_value = value / 127.0
            
            LOG.info(f"Setting CC {cc_num}={normalized_value} (original value: {value})")
            self.voice_manager.set_cc(cc_num, normalized_value)
            
            # Debug the internal state
            if cc_num == 1:  # Modulation wheel
                LOG.info(f"Mod wheel value: {normalized_value}, current_cutoff: {self.voice_manager.current_cutoff}")
                cutoff_value = self.voice_manager.current_cutoff
                
                # Send to UI
                self.send_ui_param("cutoff", cutoff_value)
                self.send_ui_status("info", f"Cutoff: {cutoff_value:.2f} Hz (mod: {normalized_value:.2f})")
                
                # Also forward directly to any connected UI.py using /cutoff endpoint
                # This ensures parameter displays in UI.py get updated
                self.forward_param_to_voices("/cutoff", cutoff_value)
            
            # Send to UI - map common CCs
            if cc_num == 1:  # Modulation wheel
                self.send_ui_param("modulation", normalized_value)
                self.send_ui_status("info", f"Mod Wheel: {normalized_value:.2f}")
            elif cc_num == 11:  # Expression
                self.send_ui_param("expression", normalized_value)
            else:
                self.send_ui_param(f"cc{cc_num}", normalized_value)
    
    def handle_pitch_bend(self, address: str, *args: Any) -> None:
        """
        Handle pitch bend messages.
        
        Args:
            address: OSC address
            *args: OSC arguments (bend_value)
        """
        if len(args) < 1:
            LOG.warning(f"Invalid pitch_bend message: {args}")
            return
        
        bend_value = float(args[0])  # -1.0 to 1.0
        self.voice_manager.set_pitch_bend(bend_value)
        
        # Send to UI
        self.send_ui_param("pitch_bend", bend_value)
    
    def handle_aftertouch(self, address: str, *args: Any) -> None:
        """
        Handle channel aftertouch.
        
        Args:
            address: OSC address
            *args: OSC arguments (pressure)
        """
        if len(args) < 1:
            LOG.warning(f"Invalid aftertouch message: {args}")
            return
        
        pressure = float(args[0])
        # Apply to all active voices
        for note, voice_idx in self.voice_manager.active_notes.items():
            voice = self.voice_manager.voices[voice_idx]
            if voice:
                voice.send_osc("/gain", pressure)
                LOG.debug(f"Channel aftertouch: applied to note {note} pressure {pressure:.2f}")
        
        # Send to UI
        self.send_ui_param("aftertouch", pressure)
    
    def handle_poly_aftertouch(self, address: str, *args: Any) -> None:
        """
        Handle polyphonic aftertouch.
        
        Args:
            address: OSC address
            *args: OSC arguments (note, pressure)
        """
        if len(args) < 2:
            LOG.warning(f"Invalid poly_aftertouch message: {args}")
            return
        
        note = int(args[0])
        pressure = float(args[1])
        
        # Find voice playing this note (if any)
        if note in self.voice_manager.active_notes:
            voice_idx = self.voice_manager.active_notes[note]
            voice = self.voice_manager.voices[voice_idx]
            if voice:
                voice.send_osc("/gain", pressure)
                LOG.info(f"Poly aftertouch: note {note} pressure {pressure:.2f}")
                
                # Send to UI
                self.send_ui_param(f"poly_aftertouch_{note}", pressure)
        else:
            LOG.info(f"Poly aftertouch for inactive note {note}")
    
    def handle_set_variable(self, address: str, *args: Any) -> None:
        """
        Handle generic variable setting with pattern /router/set/[path] value.
        
        Args:
            address: OSC address
            *args: OSC arguments (var_path, value)
        """
        if len(args) < 2:
            LOG.warning(f"Invalid set variable message, need path and value: {args}")
            return
            
        var_path = args[0]
        value = args[1]
        result = self.set_variable(var_path, value)
        
        # Send to UI
        if result:
            self.send_ui_status("info", f"Set {var_path} = {value}")
            # Also try to send as a parameter update
            try:
                val_float = float(value)
                self.send_ui_param(var_path, val_float)
            except (ValueError, TypeError):
                pass  # Not a number, don't send as param
    
    def handle_get_variable(self, address: str, *args: Any) -> None:
        """
        Handle getting variable values with pattern /router/get/[path].
        
        Args:
            address: OSC address
            *args: OSC arguments (var_path)
        """
        if len(args) < 1:
            LOG.warning(f"Invalid get variable message, need path: {args}")
            return
            
        var_path = args[0]
        value = self.get_variable(var_path)
        
        # Reply to the sender with the value
        if hasattr(self.server, "client") and hasattr(self.server, "client_address"):
            reply_client = udp_client.SimpleUDPClient(self.server.client_address[0], 
                                                    self.server.client_address[1])
            reply_client.send_message(f"/router/value/{var_path}", value)
            LOG.info(f"Sent variable {var_path} = {value} to {self.server.client_address}")
            
        # Also send to UI if connected
        if self.ui_bridge.ui_client:
            if isinstance(value, (int, float)):
                self.send_ui_param(var_path, float(value))
            self.send_ui_status("info", f"{var_path} = {value}")
    
    def handle_default_cutoff(self, address: str, *args: Any) -> None:
        """
        Handle setting default cutoff frequency.
        
        Args:
            address: OSC address
            *args: OSC arguments (cutoff)
        """
        if len(args) < 1:
            return
            
        cutoff = float(args[0])
        self.voice_manager.default_cutoff = cutoff
        self.voice_manager._update_filter_cutoff()
        LOG.info(f"Set default cutoff to {cutoff} Hz")
        
        # Send to UI
        self.send_ui_param("cutoff", cutoff)
    
    def handle_synth_name(self, address: str, *args: Any) -> None:
        """
        Handle setting synth name.
        
        Args:
            address: OSC address
            *args: OSC arguments (name)
        """
        if len(args) < 1:
            return
            
        name = str(args[0])
        self.synth_name = name
        # Update all voices to use the new synth name
        for voice in self.voice_manager.voices:
            voice.synth_name = name
        LOG.info(f"Set synth name to {name}")
        
        # Send to UI
        self.send_ui_status("info", f"Set synth name to {name}")
    
    def handle_synth_host(self, address: str, *args: Any) -> None:
        """
        Handle setting synth host.
        
        Args:
            address: OSC address
            *args: OSC arguments (host)
        """
        if len(args) < 1:
            return
            
        host = str(args[0])
        self.synth_host = host
        LOG.info(f"Set default synth host to {host}")
        
        # Send to UI
        self.send_ui_status("info", f"Set synth host to {host}")
    
    def handle_wildcard(self, address: str, *args: Any) -> None:
        """
        Debug handler for all OSC messages.
        
        Args:
            address: OSC address
            *args: OSC arguments
        """
        # Skip UI feedback messages to avoid creating feedback loops or encoding errors
        if address.startswith('/ui/status') or address.startswith('/ui/param'):
            return
            
        if not address.startswith('/router/'):
            LOG.debug(f"Received unhandled OSC: {address} {args}")
        elif '/router/get' not in address and '/router/value' not in address:
            # Log all router messages except the frequent get/value ones
            LOG.info(f"Router message: {address} {args}")
    
    def handle_all_notes_off(self, address: str, *args: Any) -> None:
        """
        Handle all notes off message.
        
        Args:
            address: OSC address
            *args: OSC arguments
        """
        self.voice_manager.all_notes_off()
        
        # Send additional emergency commands to clear all voices
        for voice in self.voice_manager.voices:
            # Send direct note off commands to each voice
            voice.send_osc("/gate", 0)
            voice.send_osc("/allNotesOff", 1)
            voice.send_osc("/panic", 1)
            voice.is_active = False
        
        # Clear all state
        self.voice_manager.active_notes.clear()
        self.voice_manager.sustained_notes.clear()
        self.voice_manager.note_off_cache.clear()
        self.voice_manager.sustain_active = False
        
        # Turn off sustain pedal for all voices
        for voice in self.voice_manager.voices:
            voice.set_sustain(0.0)
            
        LOG.info("All notes off - emergency clear complete")
        
        # Send to UI
        self.send_ui_status("warning", "All notes off - emergency clear")
    
    def handle_param_all_voices(self, address: str, *args: Any) -> None:
        """
        Handle setting a parameter on all voices.
        
        Args:
            address: OSC address
            *args: OSC arguments (param_name, value)
        """
        if len(args) < 2:
            LOG.warning(f"Invalid param_all message, need param name and value: {args}")
            return
            
        # Extract the parameter name and value
        param_name = str(args[0])
        value = float(args[1]) if len(args) > 1 else 0.0
        
        # Store any patch settings in the voice manager for reference
        # This collects parameters like mod_depth, pitch_bend_range, etc.
        if not hasattr(self.voice_manager, 'patch_settings'):
            self.voice_manager.patch_settings = {}
        
        self.voice_manager.patch_settings[param_name] = value
        
        LOG.info(f"Setting param on all voices: {param_name} = {value}")
        
        # Special handling for certain parameters
        if param_name == "cutoff":
            self.voice_manager.default_cutoff = value
            self.voice_manager._update_filter_cutoff()
            LOG.info(f"Updated default cutoff to {value:.2f}")
            
            # Apply filter cutoff
            for voice in self.voice_manager.voices:
                voice.send_osc("/cutoff", self.voice_manager.current_cutoff)
        else:
            # Regular parameter - apply to all voices
            for voice in self.voice_manager.voices:
                voice.send_osc(f"/{param_name}", value)
        
        # Send to UI
        self.send_ui_param(param_name, value)
    
    def handle_voice_reset(self, address: str, *args: Any) -> None:
        """
        Handle resetting a specific voice.
        
        Args:
            address: OSC address
            *args: OSC arguments (voice_idx)
        """
        # Extract voice index from args
        if len(args) < 1:
            LOG.warning(f"Invalid voice reset command, need voice index: {args}")
            return
            
        try:
            voice_idx = int(args[0])
            if 0 <= voice_idx < len(self.voice_manager.voices):
                voice = self.voice_manager.voices[voice_idx]
                voice.reset()
                LOG.info(f"Reset voice {voice_idx}")
                
                # Send to UI
                self.send_ui_status("warning", f"Reset voice {voice_idx}")
            else:
                LOG.warning(f"Voice index out of range: {voice_idx}")
        except (ValueError, IndexError) as e:
            LOG.warning(f"Error resetting voice: {e}")

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
        
        # Replace the voice manager
        self.voice_manager = VoiceManager(voices)
        
        # Initialize controllers for all voices (now that voice manager exists)
        self.voice_manager.reset_all_controllers()
        
        # Send to UI
        if self.ui_bridge.ui_client:
            self.send_ui_status("info", f"Created {num_voices} default voices")
        
        return True
    
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
    
    def stop(self) -> None:
        """
        Stop the OSC router gracefully.
        
        This stops the background thread and cleans up resources.
        """
        self.running = False
        
        # Close server socket if it exists
        if hasattr(self, 'server') and self.server:
            try:
                LOG.info("Closing OSC router server socket")
                self.server.server_close()
            except Exception as e:
                LOG.error(f"Error closing server socket: {e}")
        
        # Send all notes off message to voices
        if hasattr(self, 'voice_manager'):
            try:
                LOG.info("Sending all notes off to all voices")
                self.handle_all_notes_off("/all_notes_off")
            except Exception as e:
                LOG.error(f"Error sending all notes off: {e}")
                
        LOG.info("OSC Router stopped")

    def set_variable(self, var_path: str, value: Any) -> bool:
        """
        Set a router variable by path.
        
        Args:
            var_path: Variable path
            value: Value to set
            
        Returns:
            True if variable was set successfully
        """
        return self.variable_manager.set_variable(var_path, value)
    
    def get_variable(self, var_path: str) -> Optional[Any]:
        """
        Get a router variable by path.
        
        Args:
            var_path: Variable path
            
        Returns:
            Variable value if found, None otherwise
        """
        return self.variable_manager.get_variable(var_path)

    def forward_param_to_voices(self, address: str, *args: Any) -> None:
        """
        Directly forward parameters to all voices.
        
        Args:
            address: OSC address
            *args: OSC arguments (value)
        """
        if len(args) < 1:
            LOG.warning(f"Invalid parameter message, need value: {args}")
            return
        
        value = float(args[0])
        
        # Extract parameter name from address
        param_name = address
        if address.startswith('/'):
            param_name = address[1:]  # Remove leading slash
        
        LOG.info(f"Forwarding parameter {param_name} = {value} to all voices and UIs")
        
        # Apply to all voices (active or not)
        for voice in self.voice_manager.voices:
            voice.send_osc(param_name, value)
            LOG.debug(f"Set {param_name} = {value} on voice {voice.id}")
            
        # Also send to UI components using /router/param format
        # This ensures both the main UI and any separate UI components get updated
        self.handle_param_all_voices(address, param_name, value)
        
        # Don't return anything (None by default)

    def run(self) -> None:
        """
        Start the OSC router's main INBOUND listening server.
        
        This starts the server that receives all incoming OSC messages
        from MIDI bridges, UIs, and other OSC sources.
        
        Note: For non-blocking operation, use start_in_background() instead.
        """
        try:
            # Create and start OSC server for INBOUND messages
            server = ThreadingOSCUDPServer(("0.0.0.0", self.router_port), self.dispatcher)
            LOG.info(f"OSC Router listening on 0.0.0.0:{self.router_port}")
            LOG.info(f"Routing to {len(self.voice_manager.voices)} synth voices")
            
            # Print voice details
            for i, voice in enumerate(self.voice_manager.voices):
                LOG.info(f"Voice {i}: {voice.id} on {voice.host}:{voice.port}")
            
            # Store server reference
            self.server = server
            
            # Serve forever - keep listening for INBOUND messages
            server.serve_forever()
        except KeyboardInterrupt:
            LOG.info("\nOSC Router stopped.")
        except Exception as e:
            LOG.error(f"Error starting server: {e}")
            
            # Send to UI (OUTBOUND)
            if self.ui_bridge.ui_client:
                self.send_ui_status("error", f"Router error: {str(e)}") 
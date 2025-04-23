"""
OSC Router Class - Handles OSC message routing to synth voices
"""
import yaml
import json
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer
from pythonosc import udp_client

from lib.common.utils import LOG, DEFAULT_ROUTER_PORT, DEFAULT_SYNTH_HOST, DEFAULT_SYNTH_NAME
from lib.osc_bridge.voice import Voice
from lib.osc_bridge.voice_manager import VoiceManager

class OSCRouter:
    """Routes OSC messages to multiple Faust synth instances"""
    
    def __init__(self, config_file=None, router_port=DEFAULT_ROUTER_PORT, ui_host=None, ui_port=None):
        """Initialize the OSC router with config"""
        # Store the router port
        self.router_port = router_port
        
        # UI communication client
        self.ui_host = ui_host
        self.ui_port = ui_port
        self.ui_client = None
        
        # Setup UI client if host and port provided
        if ui_host and ui_port:
            self.setup_ui_client(ui_host, ui_port)
        
        # Default synth values
        self.synth_name = DEFAULT_SYNTH_NAME
        self.synth_host = DEFAULT_SYNTH_HOST
        
        # Initialize voice manager with empty list (will populate after loading config)
        self.voice_manager = VoiceManager([])
        
        # Create OSC dispatcher
        self.dispatcher = Dispatcher()
        
        # Add default handlers
        self.add_default_handlers()
        
        # Load config if provided
        if config_file:
            self.load_config(config_file)
        
        # Initialize server
        self.server = None
        
    def setup_ui_client(self, host, port):
        """Set up OSC client for sending messages to the UI"""
        try:
            port = int(port)
            self.ui_host = host
            self.ui_port = port
            self.ui_client = udp_client.SimpleUDPClient(host, port)
            LOG.info(f"Set up UI feedback to {host}:{port}")
            # Send test message to confirm connection
            self.send_ui_status("info", "Connected to OSC router")
            return True
        except Exception as e:
            LOG.error(f"Error setting up UI client: {e}")
            return False
    
    def send_ui_status(self, status_type, message):
        """Send status message to UI"""
        if self.ui_client:
            try:
                self.ui_client.send_message("/ui/status", [status_type, message])
                LOG.debug(f"Sent UI status: {status_type} - {message}")
                return True
            except Exception as e:
                LOG.error(f"Error sending UI status: {e}")
        return False
    
    def send_ui_param(self, param_name, value):
        """Send parameter update to UI"""
        if self.ui_client:
            try:
                self.ui_client.send_message("/ui/param", [param_name, value])
                LOG.debug(f"Sent UI param: {param_name} = {value}")
                return True
            except Exception as e:
                LOG.error(f"Error sending UI param: {e}")
        return False
        
    def load_config(self, config_file):
        """Load configuration from YAML file"""
        try:
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
            
            # Configure synth globals
            synth_name = DEFAULT_SYNTH_NAME
            synth_host = DEFAULT_SYNTH_HOST
            
            if 'settings' in config:
                if 'synth_host' in config['settings']:
                    synth_host = config['settings']['synth_host']
                if 'synth_name' in config['settings']:
                    synth_name = config['settings']['synth_name']
            
            # Store the settings
            self.synth_name = synth_name
            self.synth_host = synth_host
            
            LOG.info(f"Using default synth '{synth_name}' on default host '{synth_host}'")
            
            # Load voices
            voices = []
            if 'voices' in config:
                for voice_config in config['voices']:
                    voice_id = voice_config['id']
                    port = voice_config['port']
                    # Use voice-specific host if provided, fall back to default
                    host = voice_config.get('host', synth_host)
                    # Create voice with the synth name and host
                    voice = Voice(voice_id, port, host=host, synth_name=synth_name)
                    voices.append(voice)
            
            # Create new voice manager with the loaded voices
            self.voice_manager = VoiceManager(voices)
            
            LOG.info(f"Loaded configuration from {config_file}")
            LOG.info(f"Configured {len(voices)} voices")
            
            # Notify UI if connected
            if self.ui_client:
                self.send_ui_status("info", f"Loaded {len(voices)} voices from config")
                
            return True
        except Exception as e:
            LOG.error(f"Error loading config: {e}")
            if self.ui_client:
                self.send_ui_status("error", f"Failed to load config: {str(e)}")
            return False
    
    def add_default_handlers(self):
        """Add OSC message handlers to the dispatcher"""
        # Main handlers for router control
        self.dispatcher.map("/router/note_on", self.handle_note_on)
        self.dispatcher.map("/router/note_off", self.handle_note_off)
        self.dispatcher.map("/router/sustain", self.handle_sustain)
        self.dispatcher.map("/router/cc", self.handle_cc)
        self.dispatcher.map("/router/pitch_bend", self.handle_pitch_bend)
        self.dispatcher.map("/router/aftertouch", self.handle_aftertouch)
        self.dispatcher.map("/router/poly_aftertouch", self.handle_poly_aftertouch)
        
        # Variable control handlers
        self.dispatcher.map("/router/set", self.handle_set_variable)
        self.dispatcher.map("/router/get", self.handle_get_variable)
        
        # Direct variable endpoint mappings
        self.dispatcher.map("/router/default_cutoff", self.handle_default_cutoff)
        self.dispatcher.map("/router/synth_name", self.handle_synth_name)
        self.dispatcher.map("/router/synth_host", self.handle_synth_host)
        
        # All notes off
        self.dispatcher.map("/router/all_notes_off", self.handle_all_notes_off)
        
        # Parameter handling
        self.dispatcher.map("/router/param", self.handle_param_all_voices)
        
        # Direct parameter access
        self.dispatcher.map("/cutoff", self.forward_param_to_voices)
        self.dispatcher.map("/resonance", self.forward_param_to_voices)
        self.dispatcher.map("/gain", self.forward_param_to_voices)
        self.dispatcher.map("/attack", self.forward_param_to_voices)
        self.dispatcher.map("/release", self.forward_param_to_voices)
        
        # Voice reset
        self.dispatcher.map("/router/voice/reset", self.handle_voice_reset)
        
        # UI client registration
        self.dispatcher.map("/router/register_ui", self.handle_register_ui)
        
        # Add a wildcard handler for debugging
        self.dispatcher.map("/*", self.handle_wildcard)
    
    def handle_register_ui(self, address, *args):
        """Handle UI client registration"""
        if len(args) < 2:
            LOG.warning(f"Invalid UI registration: {args}")
            return
            
        host = str(args[0])
        port = int(args[1])
        
        LOG.info(f"Registering UI client at {host}:{port}")
        self.setup_ui_client(host, port)
        
        # Send current state to UI
        self.send_ui_status("info", f"Router active with {len(self.voice_manager.voices)} voices")
    
    def handle_note_on(self, address, *args):
        """Handle note on messages from MIDI-OSC bridge"""
        if len(args) < 2:
            LOG.warning(f"Invalid note_on message: {args}")
            return
        
        note = int(args[0])
        velocity = float(args[1])
        self.voice_manager.note_on(note, velocity)
        
        # Send to UI
        self.send_ui_status("note", f"Note On: {note} (vel: {velocity:.2f})")
    
    def handle_note_off(self, address, *args):
        """Handle note off messages from MIDI-OSC bridge"""
        if len(args) < 1:
            LOG.warning(f"Invalid note_off message: {args}")
            return
        
        note = int(args[0])
        self.voice_manager.note_off(note)
        
        # Send to UI
        self.send_ui_status("note", f"Note Off: {note}")
    
    def handle_sustain(self, address, *args):
        """Handle sustain pedal messages"""
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
    
    def handle_cc(self, address, *args):
        """Handle CC messages"""
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
    
    def handle_pitch_bend(self, address, *args):
        """Handle pitch bend messages"""
        if len(args) < 1:
            LOG.warning(f"Invalid pitch_bend message: {args}")
            return
        
        bend_value = float(args[0])  # -1.0 to 1.0
        self.voice_manager.set_pitch_bend(bend_value)
        
        # Send to UI
        self.send_ui_param("pitch_bend", bend_value)
        
    def handle_aftertouch(self, address, *args):
        """Handle channel aftertouch"""
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
    
    def handle_poly_aftertouch(self, address, *args):
        """Handle polyphonic aftertouch"""
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
    
    def handle_set_variable(self, address, *args):
        """Handle generic variable setting with pattern /router/set/[path] value"""
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
        
    def handle_get_variable(self, address, *args):
        """Handle getting variable values with pattern /router/get/[path]"""
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
        if self.ui_client:
            if isinstance(value, (int, float)):
                self.send_ui_param(var_path, float(value))
            self.send_ui_status("info", f"{var_path} = {value}")
            
    def handle_default_cutoff(self, address, *args):
        """Handle setting default cutoff frequency"""
        if len(args) < 1:
            return
            
        cutoff = float(args[0])
        self.voice_manager.default_cutoff = cutoff
        self.voice_manager._update_filter_cutoff()
        LOG.info(f"Set default cutoff to {cutoff} Hz")
        
        # Send to UI
        self.send_ui_param("cutoff", cutoff)
        
    def handle_synth_name(self, address, *args):
        """Handle setting synth name"""
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
        
    def handle_synth_host(self, address, *args):
        """Handle setting synth host"""
        if len(args) < 1:
            return
            
        host = str(args[0])
        self.synth_host = host
        LOG.info(f"Set default synth host to {host}")
        
        # Send to UI
        self.send_ui_status("info", f"Set synth host to {host}")
        
    def handle_wildcard(self, address, *args):
        """Debug handler for all OSC messages"""
        if not address.startswith('/router/'):
            LOG.debug(f"Received unhandled OSC: {address} {args}")
        elif '/router/get' not in address and '/router/value' not in address:
            # Log all router messages except the frequent get/value ones
            LOG.info(f"Router message: {address} {args}")
    
    def handle_all_notes_off(self, address, *args):
        """Handle all notes off message"""
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
        
    def handle_param_all_voices(self, address, *args):
        """Handle setting a parameter on all active voices"""
        LOG.info(f"Parameter change request received: {address} {args}")
        
        if len(args) < 2:
            LOG.warning(f"Invalid param message, need param_name and value: {args}")
            return
            
        # First arg is parameter name, second is value
        param_name = args[0]
        value = float(args[1])
        
        LOG.info(f"Setting parameter {param_name} = {value} on all voices")
        
        active_count = 0
        # Apply to all voices
        for voice in self.voice_manager.voices:
            if voice.is_active:
                voice.send_osc(f"/{param_name}", value)
                active_count += 1
                LOG.debug(f"Set {param_name} = {value} on voice {voice.id}")
        
        if active_count > 0:            
            LOG.info(f"Set {param_name} = {value} on {active_count} active voices")
        else:
            LOG.info(f"No active voices to set {param_name} = {value}")
            # Fallback: send to all voices regardless of active state
            for voice in self.voice_manager.voices:
                voice.send_osc(f"/{param_name}", value)
        
        # Always update UI with parameter changes
        # This ensures other UI components get updated with parameter values
        self.send_ui_param(param_name, value)
        
        # Also update special parameters like cutoff when they change via other means
        if param_name == "cutoff":
            # Update internal state to keep it in sync
            self.voice_manager.default_cutoff = value
            # Only update if this wasn't caused by modulation wheel
            if self.voice_manager.mod_wheel_value < 0.01:
                self.voice_manager.current_cutoff = value
    
    def handle_voice_reset(self, address, *args):
        """Handle resetting a specific voice"""
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

    def create_default_voices(self, num_voices=4, start_port=5510):
        """Create default voices if no config is provided"""
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
        if self.ui_client:
            self.send_ui_status("info", f"Created {num_voices} default voices")
        
        return True
    
    def run(self):
        """Start the OSC router"""
        try:
            # Create and start OSC server
            server = ThreadingOSCUDPServer(("0.0.0.0", self.router_port), self.dispatcher)
            LOG.info(f"OSC Router listening on 0.0.0.0:{self.router_port}")
            LOG.info(f"Routing to {len(self.voice_manager.voices)} synth voices")
            
            # Print voice details
            for i, voice in enumerate(self.voice_manager.voices):
                LOG.info(f"Voice {i}: {voice.id} on {voice.host}:{voice.port}")
            
            # Store server reference
            self.server = server
            
            # Serve forever
            server.serve_forever()
        except KeyboardInterrupt:
            LOG.info("\nOSC Router stopped.")
        except Exception as e:
            LOG.error(f"Error starting server: {e}")
            
            # Send to UI
            if self.ui_client:
                self.send_ui_status("error", f"Router error: {str(e)}")

    def set_variable(self, var_path, value):
        """Set a variable by path"""
        LOG.info(f"Setting variable {var_path} to {value}")
        
        # Parse the path
        parts = var_path.strip('/').split('/')
        
        # Router settings
        if parts[0] == 'router':
            if len(parts) == 1:
                LOG.warning(f"Invalid router variable path: {var_path}")
                return False
                
            if parts[1] == 'synth_name':
                self.synth_name = str(value)
                for voice in self.voice_manager.voices:
                    voice.synth_name = self.synth_name
                LOG.info(f"Set synth name to {self.synth_name}")
                return True
                
            elif parts[1] == 'synth_host':
                self.synth_host = str(value)
                LOG.info(f"Set synth host to {self.synth_host}")
                return True
                
            elif parts[1] == 'router_port':
                # Can't change port while running
                LOG.warning("Cannot change router port while running")
                return False
                
        # Voice manager settings
        elif parts[0] == 'voice_manager':
            if len(parts) == 1:
                LOG.warning(f"Invalid voice manager variable path: {var_path}")
                return False
                
            if parts[1] == 'default_cutoff':
                self.voice_manager.default_cutoff = float(value)
                self.voice_manager._update_filter_cutoff()
                LOG.info(f"Set default cutoff to {value}")
                return True
                
            elif parts[1] == 'sustain_active':
                self.voice_manager.set_sustain(float(value))
                LOG.info(f"Set sustain to {value}")
                return True
                
            # Support for other voice manager variables
                
        # Voice settings
        elif parts[0] == 'voice':
            if len(parts) < 3:
                LOG.warning(f"Invalid voice variable path: {var_path}")
                return False
                
            try:
                voice_idx = int(parts[1])
                if voice_idx < 0 or voice_idx >= len(self.voice_manager.voices):
                    LOG.warning(f"Voice index out of range: {voice_idx}")
                    return False
                    
                voice = self.voice_manager.voices[voice_idx]
                
                if parts[2] == 'port':
                    # Can't change port while running
                    LOG.warning("Cannot change voice port while running")
                    return False
                    
                elif parts[2] == 'host':
                    voice.host = str(value)
                    # Update the client
                    voice.client = udp_client.SimpleUDPClient(voice.host, voice.port)
                    LOG.info(f"Set voice {voice_idx} host to {value}")
                    return True
                    
                elif parts[2] == 'synth_name':
                    voice.synth_name = str(value)
                    LOG.info(f"Set voice {voice_idx} synth name to {value}")
                    return True
                    
            except (ValueError, IndexError) as e:
                LOG.warning(f"Error setting voice variable: {e}")
                return False
                
        # Unknown path
        LOG.warning(f"Unknown variable path: {var_path}")
        return False
        
    def get_variable(self, var_path):
        """Get a variable by path"""
        LOG.info(f"Getting variable {var_path}")
        
        # Parse the path
        parts = var_path.strip('/').split('/')
        
        # Router settings
        if parts[0] == 'router':
            if len(parts) == 1:
                # Return list of available router variables
                return json.dumps(['synth_name', 'synth_host', 'router_port'])
                
            if parts[1] == 'synth_name':
                return self.synth_name
                
            elif parts[1] == 'synth_host':
                return self.synth_host
                
            elif parts[1] == 'router_port':
                return self.router_port
                
            elif parts[1] == 'voices':
                # Return count of voices
                return len(self.voice_manager.voices)
                
        # Voice manager settings
        elif parts[0] == 'voice_manager':
            if len(parts) == 1:
                # Return list of available voice manager variables
                return json.dumps(['default_cutoff', 'current_cutoff', 'sustain_active', 
                                'mod_wheel_value', 'expression_value', 'pitch_bend',
                                'active_notes', 'sustained_notes'])
                
            if parts[1] == 'default_cutoff':
                return self.voice_manager.default_cutoff
                
            elif parts[1] == 'current_cutoff':
                return self.voice_manager.current_cutoff
                
            elif parts[1] == 'sustain_active':
                return 1.0 if self.voice_manager.sustain_active else 0.0
                
            elif parts[1] == 'mod_wheel_value':
                return self.voice_manager.mod_wheel_value
                
            elif parts[1] == 'expression_value':
                return self.voice_manager.expression_value
                
            elif parts[1] == 'pitch_bend':
                return self.voice_manager.pitch_bend
                
            elif parts[1] == 'active_notes':
                return json.dumps(list(self.voice_manager.active_notes.keys()))
                
            elif parts[1] == 'sustained_notes':
                return json.dumps(list(self.voice_manager.sustained_notes))
                
        # Voice settings
        elif parts[0] == 'voice':
            if len(parts) == 1:
                # Return list of voice indices
                return json.dumps(list(range(len(self.voice_manager.voices))))
                
            try:
                voice_idx = int(parts[1])
                if voice_idx < 0 or voice_idx >= len(self.voice_manager.voices):
                    LOG.warning(f"Voice index out of range: {voice_idx}")
                    return None
                    
                voice = self.voice_manager.voices[voice_idx]
                
                if len(parts) == 2:
                    # Return list of available voice variables
                    return json.dumps(['id', 'port', 'host', 'synth_name', 'note', 'velocity', 'is_active'])
                    
                if parts[2] == 'id':
                    return voice.id
                    
                elif parts[2] == 'port':
                    return voice.port
                    
                elif parts[2] == 'host':
                    return voice.host
                    
                elif parts[2] == 'synth_name':
                    return voice.synth_name
                    
                elif parts[2] == 'note':
                    return voice.note if voice.note is not None else -1
                    
                elif parts[2] == 'velocity':
                    return voice.velocity
                    
                elif parts[2] == 'is_active':
                    return 1.0 if voice.is_active else 0.0
                    
            except (ValueError, IndexError) as e:
                LOG.warning(f"Error getting voice variable: {e}")
                return None
                
        # Unknown path
        LOG.warning(f"Unknown variable path: {var_path}")
        return None

    def forward_param_to_voices(self, address, *args):
        """Directly forward parameters to all voices"""
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
        
        return True 
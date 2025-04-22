#!/usr/bin/env python3
"""
OSC Synth Router - Polyphonic voice allocator for OSC-controlled synths
"""
import argparse
import json
import sys
import time
import threading
import yaml
from pythonosc import udp_client
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
LOG = logging.getLogger(__name__)

# Default settings
DEFAULT_ROUTER_PORT = 9000
DEFAULT_SYNTH_HOST = "127.0.0.1"
DEFAULT_SYNTH_NAME = "simple"

def midi_to_freq(note, pitch_bend=0.0):
    """Convert MIDI note to frequency with pitch bend
    pitch_bend should be in range -1.0 to 1.0 (typically from pitch wheel)
    """
    # Apply pitch bend (default ±2 semitones)
    bend_range = 2.0  # semitones
    note = note + (pitch_bend * bend_range)
    return 440.0 * (2 ** ((note - 69) / 12))

class Voice:
    """Represents a voice instance with its state"""
    def __init__(self, voice_id, port, host=DEFAULT_SYNTH_HOST, synth_name=DEFAULT_SYNTH_NAME):
        self.id = voice_id
        self.port = port
        self.host = host
        self.synth_name = synth_name
        self.note = None
        self.velocity = 0
        self.is_active = False
        self.client = udp_client.SimpleUDPClient(self.host, port)
    
    def __repr__(self):
        return f"Voice(id={self.id}, port={self.port}, host={self.host}, note={self.note}, active={self.is_active})"
    
    def note_on(self, note, velocity):
        """Send note-on messages to this voice"""
        self.note = note
        self.velocity = velocity
        self.is_active = True
        
        # Send the three standard synth parameters
        self.send_osc("/freq", midi_to_freq(note))
        self.send_osc("/gain", velocity)
        self.send_osc("/gate", 1)
        
        LOG.debug(f"Voice {self.id} note ON: {note} vel: {velocity:.2f}")
        return True
    
    def note_off(self):
        """Send note-off message to this voice"""
        if self.is_active:
            self.send_osc("/gate", 0)
            self.is_active = False
            LOG.debug(f"Voice {self.id} note OFF: {self.note}")
            return True
        return False
    
    def reset(self):
        """Reset this voice to idle state"""
        self.note_off()
        self.note = None
        self.velocity = 0
        return True
        
    def set_cc(self, cc_num, value):
        """Send CC message to this voice"""
        # Send specific CC value
        self.send_osc(f"/cc{cc_num}", value)
        
        # Special handling for sustain pedal
        if cc_num == 64:
            # Also send to dedicated sustain parameter if it exists
            self.send_osc("/sustain", 1.0 if value >= 0.5 else 0.0)
        
        return True
    
    def set_sustain(self, value):
        """Send sustain directly (0.0-1.0)"""
        self.send_osc("/sustain", value)
        return True
    
    def set_param(self, param, value):
        """Send generic parameter to this voice"""
        self.send_osc(f"/{param}", value)
        return True
        
    def send_osc(self, path, value):
        """Send OSC message to this voice's synth instance"""
        if not path.startswith("/"):
            path = "/" + path
            
        # Format: /synthName/param
        full_path = f"/{self.synth_name}{path}"
        
        # Ensure value is float for Faust
        if isinstance(value, (int, float)):
            value = float(value)
        
        try:
            self.client.send_message(full_path, value)
            return True
        except Exception as e:
            LOG.error(f"Error sending to {self.id} ({self.host}:{self.port}): {e}")
            return False


class VoiceManager:
    """Manages allocation of voices for a polyphonic synth"""
    
    def __init__(self, voices):
        """Initialize with a list of Voice instances"""
        self.voices = voices
        self.active_notes = {}  # Maps MIDI note number to voice ID
        self.sustained_notes = set()  # Notes being sustained
        self.note_off_cache = {}  # Cache for note-off events while sustain is active
        self.sustain_active = False
        self.cc_values = {}  # Store CC values
        
        # Default controller values
        self.cc_defaults = {
            1: 0,  # Modulation wheel default (0)
        }
        
        # New attributes for filter cutoff control
        self.default_cutoff = 1000.0  # Default filter cutoff value
        self.current_cutoff = self.default_cutoff
        self.mod_wheel_value = 0.0
        self.expression_value = 0.0
        
        # Initialize pitch bend value
        self.pitch_bend = 0.0
        
        # Prepare voices
        for voice in self.voices:
            voice.reset()
            
        # No controllers to reset yet, so we don't call this immediately
        # It will be called when the router is fully set up
    
    def allocate_voice(self, note_num):
        """Allocate an available voice to a note number"""
        # Check if note is already playing
        if note_num in self.active_notes:
            return self.voices[self.active_notes[note_num]]
        
        # Find available voice
        free_voice = None
        for i, voice in enumerate(self.voices):
            if not voice.is_active:
                free_voice = voice
                self.active_notes[note_num] = i
                LOG.debug(f"Allocated voice {i} to note {note_num}")
                break
        
        # If no free voice, steal oldest
        if free_voice is None and self.voices:
            # Simple implementation - just take the first voice (could be improved)
            free_voice = self.voices[0]
            stolen_note = free_voice.note
            LOG.info(f"Stealing voice 0 from note {stolen_note}")
            
            # Send note-off to the stolen voice
            if stolen_note is not None:
                if stolen_note in self.active_notes:
                    del self.active_notes[stolen_note]
                if stolen_note in self.sustained_notes:
                    self.sustained_notes.remove(stolen_note)
                free_voice.note_off()
            
            # Assign the voice to the new note
            self.active_notes[note_num] = 0
        
        return free_voice
    
    def note_on(self, note_num, velocity):
        """Process note-on for a specific note number"""
        # If note was in sustain cache, remove it
        if note_num in self.note_off_cache:
            del self.note_off_cache[note_num]
        
        voice = self.allocate_voice(note_num)
        if voice:
            voice.note_on(note_num, velocity)
            LOG.info(f"Note ON: {note_num} velocity: {velocity:.2f}")
            return True
        
        LOG.warning(f"Could not allocate voice for note {note_num}")
        return False
    
    def note_off(self, note_num):
        """Turn off a note"""
        # Check if this note is active
        if note_num in self.active_notes:
            voice_idx = self.active_notes[note_num]
            
            # If sustain is active, cache the note-off but DO NOT remove from active_notes
            # This is the key fix - we need to keep track of notes in both places
            if self.sustain_active:
                LOG.info(f"Sustaining note {note_num} on voice {voice_idx}")
                self.sustained_notes.add(note_num) 
                self.note_off_cache[note_num] = voice_idx
                # We don't delete from active_notes while sustain is active
                # This ensures we can track which voices are playing which notes
            else:
                # Process the note-off immediately
                self._process_note_off(note_num, voice_idx)
        else:
            LOG.info(f"Note {note_num} not active, ignoring note-off")
    
    def _process_note_off(self, note, voice_idx):
        """Actually process a note-off event"""
        LOG.info(f"Turning off note {note} on voice {voice_idx}")
        
        # Get the voice
        if voice_idx >= len(self.voices):
            LOG.error(f"Voice index {voice_idx} out of range")
            return
            
        voice = self.voices[voice_idx]
        
        # Send note-off to the voice
        if voice:
            voice.note_off()
        
        # Remove from active notes if it's still there
        if note in self.active_notes:
            del self.active_notes[note]
        
        # Remove from sustained notes if it's there
        if note in self.sustained_notes:
            self.sustained_notes.remove(note)
            
        # Remove from note_off_cache if it's there
        if note in self.note_off_cache:
            del self.note_off_cache[note]
    
    def set_sustain(self, value):
        """Set the sustain pedal state"""
        # Convert 0-1 float to on/off (if coming from OSC)
        if value <= 1.0:
            value = 127 if value >= 0.5 else 0
            
        # Sustain is active if value is 63 or higher
        new_sustain_state = value >= 63
        
        # If sustain state hasn't changed, do nothing
        if self.sustain_active == new_sustain_state:
            return
            
        # If sustain was on and is now turned off
        if self.sustain_active and not new_sustain_state:
            LOG.info(f"Sustain OFF - releasing {len(self.note_off_cache)} sustained notes")
            
            # Process all cached note-offs while keeping the dict intact during iteration
            for note, voice_idx in list(self.note_off_cache.items()):
                # Only process if the note is in sustained_notes and note_off_cache
                if note in self.sustained_notes:
                    # Actually send the note_off and update tracking
                    self._process_note_off(note, voice_idx)
                    LOG.debug(f"Released sustained note {note}")
            
            # Clear cache and sustained notes
            self.note_off_cache.clear()
            self.sustained_notes.clear()
        elif not self.sustain_active and new_sustain_state:
            LOG.info("Sustain ON")
        
        # Update sustain state
        self.sustain_active = new_sustain_state
    
    def set_pitch_bend(self, value):
        """Set pitch bend value for all active voices"""
        self.pitch_bend = value
        
        # Update frequency for all active voices
        for note, voice_idx in self.active_notes.items():
            voice = self.voices[voice_idx]
            freq = midi_to_freq(note, self.pitch_bend)
            voice.send_osc("/freq", freq)
        
        LOG.info(f"Pitch bend: {value:.2f}")
        return True
        
    def all_notes_off(self):
        """Send note-off to all active voices"""
        for voice in self.voices:
            if voice.is_active:
                voice.note_off()
        
        self.active_notes.clear()
        self.sustained_notes.clear()
        self.note_off_cache.clear()
        return True
    
    def set_cc(self, cc_num, value):
        """Set a MIDI control change value"""
        # Store the CC value
        self.cc_values[cc_num] = value
        
        # Special handling for modulation wheel (CC1)
        if cc_num == 1:
            self.mod_wheel_value = value
            self._update_filter_cutoff()
            LOG.info(f"Modulation wheel: {value:.2f} → filter cutoff updated")
        
        # Special handling for expression pedal (CC11)
        elif cc_num == 11:
            self.expression_value = value
            self._update_filter_cutoff()
            LOG.info(f"Expression pedal: {value:.2f} → filter cutoff updated")
        
        # Send to all voices regardless
        for voice in self.voices:
            voice.set_cc(cc_num, value)
            
        LOG.info(f"Set CC {cc_num} to {value:.2f}")
        return True
    
    def _update_filter_cutoff(self):
        """Update filter cutoff based on mod wheel and expression pedal"""
        # Modulation wheel affects frequency exponentially (more natural)
        # Both values should be normalized to 0-1 range at this point
        
        # Start with default cutoff
        final_cutoff = self.default_cutoff
        
        # Apply modulation wheel (CC1)
        if self.mod_wheel_value > 0:
            # Map 0-1 to a reasonable filter range (exponential feels more natural)
            # 0 = no change, 1 = 10x higher cutoff
            mod_factor = 1.0 + (9.0 * self.mod_wheel_value)
            final_cutoff *= mod_factor
        
        # Apply expression pedal (CC11) 
        if self.expression_value > 0:
            # Map 0-1 to a reasonable filter range
            # 0 = no change, 1 = 10x higher cutoff
            expr_factor = 1.0 + (9.0 * self.expression_value)
            final_cutoff *= expr_factor
        
        # Ensure cutoff is within reasonable range (20Hz - 20kHz)
        final_cutoff = min(max(final_cutoff, 20.0), 20000.0)
        
        # Update current cutoff
        self.current_cutoff = final_cutoff
        
        # Apply to all voices (not just active ones)
        for voice in self.voices:
            voice.send_osc("/cutoff", final_cutoff)
        
        LOG.info(f"Updated filter cutoff to {final_cutoff:.1f} Hz (mod: {self.mod_wheel_value:.2f}, expr: {self.expression_value:.2f})")
        return True

    def reset_all_controllers(self):
        """Reset and apply all controllers to all voices"""
        # Apply current filter cutoff state (if any)
        self._update_filter_cutoff()
        
        # Apply current sustain state to all voices
        for voice in self.voices:
            # Send sustain value to the synth
            voice.send_osc("/sustain", 1.0 if self.sustain_active else 0.0)
            LOG.debug(f"Initialized sustain for voice {voice.id} to {self.sustain_active}")
        
        return True

        
class OSCRouter:
    """Routes OSC messages to multiple Faust synth instances"""
    
    def __init__(self, config_file=None, router_port=DEFAULT_ROUTER_PORT):
        """Initialize the OSC router with config"""
        # Store the router port
        self.router_port = router_port
        
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
            
            return True
        except Exception as e:
            LOG.error(f"Error loading config: {e}")
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
        
        # Add a wildcard handler for debugging
        self.dispatcher.map("/*", self.handle_wildcard)
    
    def handle_note_on(self, address, *args):
        """Handle note on messages from MIDI-OSC bridge"""
        if len(args) < 2:
            LOG.warning(f"Invalid note_on message: {args}")
            return
        
        note = int(args[0])
        velocity = float(args[1])
        self.voice_manager.note_on(note, velocity)
    
    def handle_note_off(self, address, *args):
        """Handle note off messages from MIDI-OSC bridge"""
        if len(args) < 1:
            LOG.warning(f"Invalid note_off message: {args}")
            return
        
        note = int(args[0])
        self.voice_manager.note_off(note)
    
    def handle_sustain(self, address, *args):
        """Handle sustain pedal messages"""
        if len(args) < 1:
            LOG.warning(f"Invalid sustain message: {args}")
            return
        
        sustain_value = float(args[0])
        self.voice_manager.set_sustain(sustain_value)
        LOG.info(f"Sustain pedal changed: {sustain_value}")
    
    def handle_cc(self, address, *args):
        """Handle CC messages"""
        if len(args) < 2:
            LOG.warning(f"Invalid CC message: {args}")
            return
        
        cc_num = int(args[0])
        value = float(args[1])
        
        # Value normalization - MIDI typically sends 0-127
        if cc_num == 64:  # Sustain pedal
            # Send directly to sustain handler
            self.handle_sustain(address, value)
        else:
            # For other CCs (including modulation wheel and expression)
            # Ensure value is between 0-1 for filter cutoff calculations
            normalized_value = value
            if value > 1.0:
                normalized_value = value / 127.0
            
            self.voice_manager.set_cc(cc_num, normalized_value)
    
    def handle_pitch_bend(self, address, *args):
        """Handle pitch bend messages"""
        if len(args) < 1:
            LOG.warning(f"Invalid pitch_bend message: {args}")
            return
        
        bend_value = float(args[0])  # -1.0 to 1.0
        self.voice_manager.set_pitch_bend(bend_value)
    
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
        else:
            LOG.info(f"Poly aftertouch for inactive note {note}")
    
    def handle_set_variable(self, address, *args):
        """Handle generic variable setting with pattern /router/set/[path] value"""
        if len(args) < 2:
            LOG.warning(f"Invalid set variable message, need path and value: {args}")
            return
            
        var_path = args[0]
        value = args[1]
        self.set_variable(var_path, value)
        
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
            
    def handle_default_cutoff(self, address, *args):
        """Handle setting default cutoff frequency"""
        if len(args) < 1:
            return
            
        cutoff = float(args[0])
        self.voice_manager.default_cutoff = cutoff
        self.voice_manager._update_filter_cutoff()
        LOG.info(f"Set default cutoff to {cutoff} Hz")
        
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
        
    def handle_synth_host(self, address, *args):
        """Handle setting synth host"""
        if len(args) < 1:
            return
            
        host = str(args[0])
        self.synth_host = host
        LOG.info(f"Set default synth host to {host}")
        
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
        LOG.info("All notes off")
        
    def handle_param_all_voices(self, address, *args):
        """Handle setting a parameter on all active voices"""
        LOG.info(f"Parameter change request received: {address} {args}")
        
        if len(args) < 2:
            LOG.warning(f"Invalid param message, need param_name and value: {args}")
            return
            
        # First arg is parameter name, second is value
        param_name = args[0]
        value = float(args[1])
        
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
        
        LOG.info(f"Forwarding parameter {param_name} = {value} to all voices")
        
        # Apply to all voices (active or not)
        for voice in self.voice_manager.voices:
            voice.send_osc(param_name, value)
            LOG.debug(f"Set {param_name} = {value} on voice {voice.id}")


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="OSC Synth Router")
    parser.add_argument("-c", "--config", help="Path to config file (JSON or YAML)")
    parser.add_argument("-p", "--port", type=int, default=DEFAULT_ROUTER_PORT,
                      help=f"OSC port to listen on (default: {DEFAULT_ROUTER_PORT})")
    parser.add_argument("-v", "--voices", type=int, default=0,
                      help="Number of voices to create if no config (default: 4)")
    parser.add_argument("-s", "--start-port", type=int, default=5510,
                      help="Starting port for auto-generated voices (default: 5510)")
    
    return parser.parse_args()


def main():
    """Main entry point"""
    # Parse args
    args = parse_args()
    
    # Create the router
    router = OSCRouter(config_file=args.config, router_port=args.port)
    
    # If no config but voices specified, create default voices
    if not args.config or len(router.voice_manager.voices) == 0:
        num_voices = args.voices if args.voices > 0 else 4
        router.create_default_voices(num_voices=num_voices, start_port=args.start_port)
        LOG.info(f"Created {num_voices} default voices starting at port {args.start_port}")
    
    # Run the router
    router.run()


if __name__ == "__main__":
    main() 
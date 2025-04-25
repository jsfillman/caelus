#!/usr/bin/env python3
"""
Direct MIDI to Synth

This script bypasses the OSC router entirely and sends MIDI messages
directly to the synth. This is useful when the router isn't working properly.
"""

import argparse
import sys
import os
import time
import signal
import threading
import logging
from typing import Optional, List, Dict
import yaml
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
LOG = logging.getLogger('direct_midi')

# Add parent directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

try:
    from pythonosc import udp_client
except ImportError:
    LOG.error("Could not import pythonosc. Try: pip install python-osc")
    sys.exit(1)

class DirectMIDIToSynth:
    """Bypasses the OSC router and sends MIDI messages directly to the synth"""
    
    def __init__(self, synth_port=5510, synth_name="simple"):
        """Initialize with synth port and name"""
        self.synth_port = synth_port
        self.synth_name = synth_name
        self.synth_client = None
        self.midi_client = None
        self.running = False
        self.midi_port = None
        
        # Voice state tracking
        self.active_notes = {}  # note -> velocity
        
        # Initialize OSC client
        try:
            self.synth_client = udp_client.SimpleUDPClient("127.0.0.1", synth_port)
            LOG.info(f"Connected to synth at 127.0.0.1:{synth_port}")
        except Exception as e:
            LOG.error(f"Error connecting to synth: {e}")
            raise
    
    def start_midi_monitoring(self, port_name=None):
        """Start monitoring a MIDI port"""
        try:
            import mido
            LOG.info("Imported mido successfully")
            
            if port_name is None:
                # List available ports
                ports = mido.get_input_names()
                if not ports:
                    LOG.error("No MIDI ports available")
                    return False
                
                LOG.info("Available MIDI ports:")
                for i, port in enumerate(ports):
                    LOG.info(f"  {i+1}: {port}")
                
                # Ask user to select a port
                selection = input("Select MIDI port (number or name): ")
                try:
                    # Try to interpret as number
                    idx = int(selection) - 1
                    if 0 <= idx < len(ports):
                        port_name = ports[idx]
                    else:
                        LOG.error(f"Invalid selection: {selection}")
                        return False
                except ValueError:
                    # Use as port name
                    if selection in ports:
                        port_name = selection
                    else:
                        LOG.error(f"Unknown port: {selection}")
                        return False
            
            # Store the port name
            self.midi_port = port_name
            LOG.info(f"Selected MIDI port: {port_name}")
            
            # Start in a thread
            self.running = True
            self.midi_thread = threading.Thread(target=self._midi_thread)
            self.midi_thread.daemon = True
            self.midi_thread.start()
            
            return True
            
        except ImportError:
            LOG.error("Could not import mido. Try: pip install mido python-rtmidi")
            return False
    
    def _midi_thread(self):
        """Background thread for MIDI processing"""
        try:
            import mido
            
            # Open MIDI port
            with mido.open_input(self.midi_port) as midi_in:
                LOG.info(f"Opened MIDI port: {self.midi_port}")
                LOG.info("Ready to receive MIDI messages")
                
                # Process MIDI messages
                while self.running:
                    for msg in midi_in.iter_pending():
                        self._handle_midi_message(msg)
                    time.sleep(0.001)
                    
        except Exception as e:
            LOG.error(f"Error in MIDI thread: {e}")
            
    def _handle_midi_message(self, msg):
        """Process a MIDI message"""
        if msg.type == 'note_on':
            if msg.velocity == 0:
                # Treat as note off
                self._note_off(msg.note)
            else:
                # Regular note on
                velocity = msg.velocity / 127.0
                self._note_on(msg.note, velocity)
                
        elif msg.type == 'note_off':
            self._note_off(msg.note)
            
        elif msg.type == 'control_change':
            self._control_change(msg.control, msg.value)
            
        elif msg.type == 'pitchwheel':
            # Normalize to -1 to 1
            value = msg.pitch / 8192.0
            self._pitch_bend(value)
            
        else:
            LOG.debug(f"Unhandled MIDI message: {msg}")
    
    def _note_on(self, note, velocity):
        """Send note on to synth"""
        LOG.info(f"Note ON: {note}, velocity={velocity:.2f}")
        
        # Store the note
        self.active_notes[note] = velocity
        
        # Calculate frequency
        freq = self._midi_to_freq(note)
        
        # Send the trinity of synth parameters
        self._send_osc("freq", freq)
        self._send_osc("gain", velocity)
        self._send_osc("gate", 1)
    
    def _note_off(self, note):
        """Send note off to synth"""
        LOG.info(f"Note OFF: {note}")
        
        # Remove from active notes
        if note in self.active_notes:
            del self.active_notes[note]
        
        # Send gate off
        self._send_osc("gate", 0)
        
        # Extra insurance
        self._send_osc("allNotesOff", 1)
    
    def _control_change(self, cc_num, value):
        """Handle a CC message"""
        # Normalize to 0-1
        norm_value = value / 127.0
        
        # Special handling for certain CCs
        if cc_num == 1:  # Mod wheel
            LOG.info(f"Mod wheel: {value} ({norm_value:.2f})")
            self._send_osc("mod", norm_value)
            
        elif cc_num == 64:  # Sustain pedal
            sustain_on = value >= 64
            LOG.info(f"Sustain pedal: {'ON' if sustain_on else 'OFF'}")
            self._send_osc("sustain", 1 if sustain_on else 0)
            
        else:
            LOG.info(f"CC {cc_num}: {value}")
            self._send_osc(f"cc{cc_num}", norm_value)
    
    def _pitch_bend(self, value):
        """Handle pitch bend"""
        LOG.info(f"Pitch bend: {value:.2f}")
        
        # Apply to current note if any
        if self.active_notes:
            # Get the current note
            note = next(iter(self.active_notes.keys()))
            
            # Apply pitch bend - assuming ±2 semitones range
            freq = self._midi_to_freq(note, value, 2.0)
            self._send_osc("freq", freq)
    
    def _midi_to_freq(self, note, pitch_bend=0.0, bend_range=2.0):
        """Convert MIDI note to frequency with optional pitch bend"""
        # Apply pitch bend
        note_with_bend = note + (pitch_bend * bend_range)
        
        # Convert to frequency
        return 440.0 * (2 ** ((note_with_bend - 69) / 12))
    
    def _send_osc(self, param, value):
        """Send OSC message to synth"""
        if not self.synth_client:
            LOG.error("No synth client available")
            return False
        
        try:
            # Format OSC path with synth name
            path = f"/{self.synth_name}/{param}"
            
            # Convert types as needed
            if isinstance(value, bool):
                value = 1 if value else 0
            elif isinstance(value, (int, float)):
                value = float(value)
            
            # Send the message
            self.synth_client.send_message(path, value)
            LOG.debug(f"Sent OSC: {path} = {value}")
            return True
            
        except Exception as e:
            LOG.error(f"Error sending OSC: {e}")
            return False
    
    def stop(self):
        """Stop MIDI monitoring"""
        self.running = False
        
        # Turn off any active notes
        LOG.info("Sending all notes off")
        self._send_osc("gate", 0)
        self._send_osc("allNotesOff", 1)
        self._send_osc("panic", 1)
        
        LOG.info("MIDI to synth bridge stopped")

def load_synth_config(config_file):
    """Load synth configuration from voices.yaml"""
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        # Extract settings
        settings = config.get('settings', {})
        synth_name = settings.get('synth_name', 'simple')
        
        # Extract voice info
        voices = config.get('voices', [])
        if voices:
            first_voice = voices[0]
            port = first_voice.get('port', 5510)
            
            return {
                'synth_name': synth_name,
                'port': port
            }
        else:
            LOG.warning("No voices found in config")
            return {
                'synth_name': synth_name,
                'port': 5510
            }
            
    except Exception as e:
        LOG.error(f"Error loading config: {e}")
        return {
            'synth_name': 'simple',
            'port': 5510
        }

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Direct MIDI to Synth Bridge")
    parser.add_argument("-c", "--config", type=str,
                       help="Path to voices.yaml configuration")
    parser.add_argument("-p", "--port", type=int,
                       help="Synth port (default: 5510)")
    parser.add_argument("-n", "--name", type=str,
                       help="Synth name (default: simple)")
    parser.add_argument("-m", "--midi", type=str,
                       help="MIDI port to use")
    parser.add_argument("-d", "--detect", action="store_true",
                       help="Auto-detect voices.yaml from Simple Mono preset")
    
    args = parser.parse_args()
    
    # If detect flag is set, look for voices.yaml in presets directory
    if args.detect and not args.config:
        preset_dir = os.path.join(parent_dir, "presets", "00 - Simple Mono")
        config_path = os.path.join(preset_dir, "voices.yaml")
        
        if os.path.exists(config_path):
            LOG.info(f"Auto-detected config file: {config_path}")
            args.config = config_path
        else:
            LOG.warning(f"Could not auto-detect config file at {config_path}")
    
    # Load config if provided
    synth_port = args.port or 5510
    synth_name = args.name or 'simple'
    
    if args.config:
        config = load_synth_config(args.config)
        if not args.port:
            synth_port = config['port']
        if not args.name:
            synth_name = config['synth_name']
    
    # Create bridge
    try:
        bridge = DirectMIDIToSynth(synth_port, synth_name)
        
        # Register signal handler for clean exit
        def signal_handler(sig, frame):
            LOG.info("\nStopping bridge...")
            bridge.stop()
            sys.exit(0)
            
        signal.signal(signal.SIGINT, signal_handler)
        
        # Start MIDI monitoring
        if bridge.start_midi_monitoring(args.midi):
            LOG.info("=" * 50)
            LOG.info(f"DIRECT MIDI TO SYNTH BRIDGE STARTED")
            LOG.info("=" * 50)
            LOG.info(f"Synth port: {synth_port}")
            LOG.info(f"Synth name: {synth_name}")
            LOG.info(f"MIDI port: {bridge.midi_port}")
            LOG.info("\nThis bridge bypasses the OSC router completely.")
            LOG.info("If you hear sound now but not with Caelus, the issue is in the router.")
            LOG.info("\nPress Ctrl+C to stop.")
            
            # Run until interrupted
            while True:
                time.sleep(0.1)
                
        else:
            LOG.error("Failed to start MIDI monitoring")
            return 1
            
    except KeyboardInterrupt:
        LOG.info("\nStopping bridge...")
    except Exception as e:
        LOG.error(f"Error starting bridge: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
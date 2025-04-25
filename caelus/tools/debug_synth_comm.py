#!/usr/bin/env python3
"""
Debug tool for monitoring OSC communication with the synth.
This script loads the same voices.yaml file as the main application
and creates voice objects to test direct communication.
"""

import os
import sys
import time
import yaml
import argparse
from pythonosc import udp_client

# Add parent directory to path so we can import modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from lib.osc_bridge.voice import Voice
from lib.common.utils import LOG

def load_voices_config(config_file):
    """Load voice configuration from YAML file"""
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        # Extract settings
        settings = config.get('settings', {})
        synth_name = settings.get('synth_name', 'synth')
        synth_host = settings.get('synth_host', '127.0.0.1')
        
        # Create voice instances
        voices = []
        for i, voice_config in enumerate(config.get('voices', [])):
            voice_id = voice_config.get('id', f"voice{i}")
            port = voice_config.get('port')
            host = voice_config.get('host', synth_host)
            
            if port:
                voice = Voice(voice_id, port, host=host, synth_name=synth_name)
                voices.append(voice)
                LOG.info(f"Created voice: {voice}")
        
        LOG.info(f"Loaded {len(voices)} voices with synth_name='{synth_name}'")
        return settings, voices
    except Exception as e:
        LOG.error(f"Error loading voice config: {e}")
        return {}, []

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Debug synth OSC communication")
    parser.add_argument("--config", type=str, default="presets/00 - Simple Mono/voices.yaml", 
                        help="Path to voices.yaml configuration")
    parser.add_argument("--osc-dump", action="store_true", 
                        help="Enable detailed OSC message dumping")
    
    args = parser.parse_args()
    
    # Load configuration
    settings, voices = load_voices_config(args.config)
    
    if not voices:
        LOG.error(f"No voices loaded from {args.config}")
        return 1
    
    # Print loaded configuration
    LOG.info(f"Configuration from {args.config}:")
    LOG.info(f"  Synth name: {settings.get('synth_name')}")
    LOG.info(f"  Synth host: {settings.get('synth_host')}")
    LOG.info(f"  Number of voices: {len(voices)}")
    
    # Enable OSC message debugging if requested
    if args.osc_dump:
        # Backup the original send_osc method
        original_send_osc = Voice.send_osc
        
        # Create a debugging wrapper
        def debug_send_osc(self, path, value):
            LOG.info(f"OSC DEBUG: Voice {self.id} sending: {path} = {value} to {self.host}:{self.port}")
            result = original_send_osc(self, path, value)
            LOG.info(f"OSC DEBUG: Result = {result}")
            return result
        
        # Replace the method with our debugging version
        Voice.send_osc = debug_send_osc
        LOG.info("Enabled detailed OSC message debugging")
    
    # Test each voice with various commands
    for i, voice in enumerate(voices):
        LOG.info(f"\nTesting voice {i}: {voice}")
        
        # Test reset
        LOG.info(f"  Resetting voice...")
        voice.reset()
        time.sleep(0.1)
        
        # Test note on
        LOG.info(f"  Sending note_on (60, 0.8)...")
        voice.note_on(60, 0.8)  # Middle C, velocity 0.8
        time.sleep(0.5)
        
        # Test parameter change
        LOG.info(f"  Setting parameter 'cutoff' to 2000...")
        voice.set_param("cutoff", 2000.0)
        time.sleep(0.5)
        
        # Play a few more notes to test voice allocation
        LOG.info(f"  Playing a scale...")
        for note in [62, 64, 65, 67, 69, 71, 72]:  # D, E, F, G, A, B, C
            voice.note_on(note, 0.8)
            time.sleep(0.2)
            voice.note_off()
            time.sleep(0.1)
        
        # Test note off
        LOG.info(f"  Sending note_off...")
        voice.note_off()
        time.sleep(0.5)
    
    LOG.info("\nTest completed. If you heard sound, the communication is working!")
    LOG.info("If not, check the settings in voices.yaml and the synth process.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
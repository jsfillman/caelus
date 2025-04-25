#!/usr/bin/env python3
"""
Debug OSC Router

This script runs a standalone OSC router with debug logging enabled.
It's useful for diagnosing issues with the voice allocation and OSC message routing.

Usage:
1. Stop Caelus if it's running
2. Run this script with the config file path from the current bank
3. Use tools/inject_midi.py to simulate MIDI input
4. Check logs for debug information
"""

import sys
import os
import time
import argparse
import signal
import logging
from pathlib import Path

# Add parent directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Set up logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
LOG = logging.getLogger("debug_router")

# Import the debug router
try:
    from lib.osc_bridge.router_debug import OSCRouterDebug
except ImportError:
    LOG.error("Could not import OSCRouterDebug. Make sure router_debug.py is in lib/osc_bridge/")
    sys.exit(1)

def main():
    """Run the debug router"""
    parser = argparse.ArgumentParser(description="Run Debug OSC Router")
    parser.add_argument("-c", "--config", type=str, default=None,
                      help="Path to voices.yaml configuration file")
    parser.add_argument("-p", "--port", type=int, default=9000,
                      help="Router port (default: 9000)")
    parser.add_argument("-d", "--detect", action="store_true",
                      help="Auto-detect voices.yaml from Simple Mono preset")
    parser.add_argument("-v", "--voices", type=int, default=1, 
                      help="Number of voices to create if no config provided (default: 1)")
    
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
            LOG.warning("Will create default voices instead")
    
    # Create router
    router = OSCRouterDebug(args.config, args.port)
    
    # If no config provided, create default voices
    if not args.config:
        LOG.info(f"No config provided, creating {args.voices} default voices")
        router.create_default_voices(args.voices)
    
    # Set up signal handler for clean exit
    def signal_handler(sig, frame):
        LOG.info("Stopping router...")
        router.running = False
        sys.exit(0)
        
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Start router
        LOG.info(f"Starting debug router on port {args.port}")
        router.start_in_background()
        
        # Print router info
        LOG.info(f"Router info:")
        LOG.info(f"  Synth name: {router.synth_name}")
        LOG.info(f"  Synth host: {router.synth_host}")
        LOG.info(f"  Voice count: {len(router.voice_manager.voices)}")
        
        # Print voice info
        LOG.info("Voice info:")
        for i, voice in enumerate(router.voice_manager.voices):
            LOG.info(f"  Voice {i}: id={voice.id}, port={voice.port}, host={voice.host}, synth_name={voice.synth_name}")
        
        LOG.info("\nRouter is running. Use tools/inject_midi.py to simulate MIDI input.")
        LOG.info("Press Ctrl+C to stop.")
        
        # Keep the main thread alive
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        LOG.info("Stopping router...")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
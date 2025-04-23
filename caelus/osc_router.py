#!/usr/bin/env python3
"""
OSC Synth Router - Polyphonic voice allocator for OSC-controlled synths
"""
import argparse
import sys

from lib.common.utils import LOG, DEFAULT_ROUTER_PORT
from lib.osc_bridge.router import OSCRouter

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
    parser.add_argument("--ui-host", type=str, help="Host for sending UI feedback")
    parser.add_argument("--ui-port", type=int, help="Port for sending UI feedback")
    
    return parser.parse_args()


def main():
    """Main entry point"""
    # Parse args
    args = parse_args()
    
    # Create the router
    router = OSCRouter(config_file=args.config, router_port=args.port, 
                       ui_host=args.ui_host, ui_port=args.ui_port)
    
    # If no config but voices specified, create default voices
    if not args.config or len(router.voice_manager.voices) == 0:
        num_voices = args.voices if args.voices > 0 else 4
        router.create_default_voices(num_voices=num_voices, start_port=args.start_port)
        LOG.info(f"Created {num_voices} default voices starting at port {args.start_port}")
    
    # Run the router
    router.run()


if __name__ == "__main__":
    main() 
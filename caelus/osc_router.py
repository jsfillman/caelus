#!/usr/bin/env python3
"""
OSC Synth Router - Polyphonic voice allocator for OSC-controlled synths.

This script serves as the entry point for the OSC router system, which manages
polyphonic voice allocation for synthesizers controlled via OSC.
"""
import argparse
import sys
from typing import Optional, Tuple

from lib.common.utils import LOG, DEFAULT_ROUTER_PORT
from lib.osc_bridge.router import OSCRouter


def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments.
    
    Returns:
        Parsed command line arguments
    """
    parser = argparse.ArgumentParser(description="OSC Synth Router")
    parser.add_argument("-c", "--config", help="Path to config file (JSON or YAML)")
    parser.add_argument(
        "-p", "--port", 
        type=int, 
        default=DEFAULT_ROUTER_PORT,
        help=f"OSC port to listen on (default: {DEFAULT_ROUTER_PORT})"
    )
    parser.add_argument(
        "-v", "--voices", 
        type=int, 
        default=0,
        help="Number of voices to create if no config (default: 4)"
    )
    parser.add_argument(
        "-s", "--start-port", 
        type=int, 
        default=5510,
        help="Starting port for auto-generated voices (default: 5510)"
    )
    parser.add_argument(
        "--ui-host", 
        type=str, 
        help="Host for sending UI feedback"
    )
    parser.add_argument(
        "--ui-port", 
        type=int, 
        help="Port for sending UI feedback"
    )
    
    return parser.parse_args()


def main() -> int:
    """
    Main entry point for the OSC router.
    
    Returns:
        Exit code (0 for success, non-zero for error)
    """
    # Parse args
    args = parse_args()
    
    try:
        # Create the router
        router = OSCRouter(
            config_file=args.config, 
            router_port=args.port, 
            ui_host=args.ui_host, 
            ui_port=args.ui_port
        )
        
        # If no config but voices specified, create default voices
        if not args.config or len(router.voice_manager.voices) == 0:
            num_voices = args.voices if args.voices > 0 else 4
            router.create_default_voices(
                num_voices=num_voices, 
                start_port=args.start_port
            )
            LOG.info(f"Created {num_voices} default voices starting at port {args.start_port}")
        
        # Run the router
        router.run()
        return 0
    
    except KeyboardInterrupt:
        LOG.info("Router stopped by user")
        return 0
    except Exception as e:
        LOG.error(f"Error running router: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 
#!/usr/bin/env python3
"""
OSC Synth Router - Polyphonic voice allocator for OSC-controlled synths.

The traffic cop of the MIDI highway - routes notes to the right synth instances
at the right time, preventing 10-car pileups and ensuring your performance 
doesn't sound like a cat walking across a piano.
"""
import argparse
import sys
import os
from typing import Optional, Tuple

# Add the project root to sys.path to allow importing from lib packages
# This ensures that when we run the module directly, we can still import lib modules
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from lib.common.utils import LOG, DEFAULT_ROUTER_PORT
from lib.osc_bridge.router import OSCRouter


def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments.
    
    Translates human intentions into machine-readable instructions.
    Command line args: the OG user interface since 1970.
    
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
    parser.add_argument(
        "--background",
        action="store_true",
        help="Run router in background (non-blocking)"
    )
    
    return parser.parse_args()


def main() -> int:
    """
    Main entry point for the OSC router.
    
    Where the magic happens - connects the dots between MIDI input,
    voice allocation, and your ears' pleasure centers.
    
    Returns:
        Exit code (0 for success, non-zero for error)
    """
    # Parse args
    args = parse_args()
    
    try:
        # Create the router - our traffic controller for the MIDI highway
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
        
        # Run the router - engage warp drive!
        if args.background:
            # Run in background (non-blocking)
            router.start_in_background()
            # Keep the process alive but don't block
            import time
            while True:
                time.sleep(1)
        else:
            # Run in foreground (blocking)
            router.run()
        return 0
    
    except KeyboardInterrupt:
        LOG.info("Router stopped by user - they must have better things to do")
        return 0
    except Exception as e:
        LOG.error(f"Error running router: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 
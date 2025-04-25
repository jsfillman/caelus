#!/usr/bin/env python3
"""
MIDI to OSC bridge for Caelus synth router.

The MIDI whisperer - captures your keyboard's intentions
and translates them into OSC packets that the router can understand.
"""
import sys
import os
import argparse
from typing import NoReturn

# Add the project root to sys.path to allow importing from lib packages
# This ensures that when we run the module directly, we can still import lib modules
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PyQt6.QtWidgets import QApplication

from lib.core.utils import LOG
from lib.midi_osc.gui import MidiOscGui

# --- Default Settings (change these if you're feeling adventurous) ---
OSC_IP: str = "127.0.0.1"  # Local is where the heart is
OSC_PORT: int = 9000       # Where the router is listening
ROUTER_NAME: str = "router" # What we call our digital traffic cop
PRESETS_DIR: str = "presets" # Where dreams are stored
UI_OSC_PORT: int = 9002    # Where we listen for the router's response

def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments.
    
    Simpler than parsing human emotions, but still necessary.
    
    Returns:
        Parsed command line arguments
    """
    parser = argparse.ArgumentParser(description="MIDI to OSC bridge for Caelus")
    parser.add_argument("--port", type=int, default=OSC_PORT, 
                       help=f"Router's OSC port (default: {OSC_PORT})")
    parser.add_argument("--ip", type=str, default=OSC_IP,
                       help=f"Router's IP address (default: {OSC_IP})")
    parser.add_argument("--router", type=str, default=ROUTER_NAME,
                       help=f"OSC router name (default: {ROUTER_NAME})")
    parser.add_argument("--presets", type=str, default=PRESETS_DIR,
                       help=f"Presets directory (default: {PRESETS_DIR})")
    parser.add_argument("--ui-port", type=int, default=UI_OSC_PORT,
                      help=f"Port for listening to router feedback (default: {UI_OSC_PORT})")
    
    return parser.parse_args()

def main() -> int:
    """
    The grand conductor of the MIDI-OSC orchestra.
    
    MIDI → OSC → Router → Synth. Simple, elegant, effective.
    
    Returns:
        Exit code (0 for success)
    """
    # Parse command line arguments
    args = parse_args()
    
    LOG.info("✨ Starting MIDI-OSC bridge ✨")
    LOG.info(f"  Router: {args.ip}:{args.port}")
    LOG.info(f"  UI feedback port: {args.ui_port}")
    
    # Create GUI application - because command lines are so 1980s
    app = QApplication(sys.argv)
    
    # Launch the bridge GUI
    window = MidiOscGui(
        osc_ip=args.ip,
        osc_port=args.port,
        router_name=args.router,
        presets_dir=args.presets,
        ui_osc_port=args.ui_port
    )
    window.resize(400, 250)
    window.show()
    
    # Enter the Qt matrix
    return app.exec() if hasattr(app, 'exec') else app.exec_()

if __name__ == "__main__":
    sys.exit(main()) 
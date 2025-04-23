#!/usr/bin/env python3
"""
MIDI to OSC bridge for Caelus synth router
"""
import sys
import argparse
from PyQt6.QtWidgets import QApplication

from lib.common.utils import LOG
from lib.midi_osc.gui import MidiOscGui

# --- Default Configuration ---
OSC_IP = "127.0.0.1"
OSC_PORT = 9001  # Default port
ROUTER_NAME = "router"
PRESETS_DIR = "presets"
UI_OSC_PORT = 9002  # Default UI OSC port for feedback from router

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="MIDI to OSC bridge for Caelus")
    parser.add_argument("--port", type=int, default=OSC_PORT, 
                       help=f"OSC port to use (default: {OSC_PORT})")
    parser.add_argument("--ip", type=str, default=OSC_IP,
                       help=f"OSC IP address to use (default: {OSC_IP})")
    parser.add_argument("--router", type=str, default=ROUTER_NAME,
                       help=f"OSC router name (default: {ROUTER_NAME})")
    parser.add_argument("--presets", type=str, default=PRESETS_DIR,
                       help=f"Presets directory (default: {PRESETS_DIR})")
    parser.add_argument("--ui-port", type=int, default=UI_OSC_PORT,
                      help=f"Port for UI to listen for router messages (default: {UI_OSC_PORT})")
    
    return parser.parse_args()

def main():
    """Main entry point"""
    # Parse command line arguments
    args = parse_args()
    
    # Override defaults with command line arguments
    osc_port = args.port
    osc_ip = args.ip
    router_name = args.router
    presets_dir = args.presets
    ui_osc_port = args.ui_port
    
    LOG.info(f"Starting MIDI-OSC bridge with:")
    LOG.info(f"  OSC router port: {osc_port}")
    LOG.info(f"  UI feedback port: {ui_osc_port}")
    LOG.info(f"  Router name: {router_name}")
    
    # Create Qt application
    app = QApplication(sys.argv)
    
    # Create and show the GUI
    window = MidiOscGui(
        osc_ip=osc_ip,
        osc_port=osc_port,
        router_name=router_name,
        presets_dir=presets_dir,
        ui_osc_port=ui_osc_port
    )
    window.resize(400, 250)
    window.show()
    
    # Run the Qt application event loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

"""
Command-line argument parsing for Caelus.

This module handles argument parsing for the Caelus synthesizer system.
"""
import argparse
from typing import Dict, Any

# Default settings - moved from main launcher
DEFAULT_ROUTER_PORT = 9000
DEFAULT_UI_PORT = 9002
DEFAULT_PRESETS_DIR = "presets"

def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments.
    
    Returns:
        Parsed command line arguments
    """
    parser = argparse.ArgumentParser(description="Caelus Synthesizer System")
    parser.add_argument("--port", type=int, default=DEFAULT_ROUTER_PORT, 
                      help=f"Router port (default: {DEFAULT_ROUTER_PORT})")
    parser.add_argument("--ip", type=str, default="127.0.0.1",
                      help="Router IP address (default: 127.0.0.1)")
    parser.add_argument("--presets", type=str, default=DEFAULT_PRESETS_DIR,
                      help=f"Presets directory (default: {DEFAULT_PRESETS_DIR})")
    parser.add_argument("--ui-port", type=int, default=DEFAULT_UI_PORT,
                      help=f"UI feedback port (default: {DEFAULT_UI_PORT})")
    parser.add_argument("--no-splash", action="store_true",
                      help="Disable splash screen")
    parser.add_argument("--default-bank", type=str,
                      help="Default bank to load on startup")
    parser.add_argument("--no-auto-start-router", action="store_true",
                      help="Don't automatically start the OSC router (for use with router-first launcher)")
    parser.add_argument("--router-name", type=str, default="router",
                      help="Router name for OSC messages (default: router)")
    
    return parser.parse_args()

def get_settings_from_args(args: argparse.Namespace) -> Dict[str, Any]:
    """
    Convert parsed arguments to a settings dictionary.
    
    Args:
        args: Parsed command line arguments
        
    Returns:
        Dictionary of settings
    """
    return {
        "router_port": args.port,
        "router_ip": args.ip,
        "presets_dir": args.presets,
        "ui_port": args.ui_port,
        "show_splash": not args.no_splash,
        "default_bank": args.default_bank,
        "no_auto_start_router": args.no_auto_start_router,
        "router_name": args.router_name,
    }
"""
Router-first launcher for Caelus.

This script implements a more robust startup sequence where:
1. Router starts first
2. It loads a default preset
3. It launches synths from the preset's voices.yaml
4. It verifies connections to the synths
5. Only then does it launch the GUI
"""
import os
import sys
import time
import subprocess
import threading
from typing import Dict, List, Optional, Any

from lib.core.utils import LOG
from lib.core.bank_manager import BankManager
from lib.midi_osc.helpers import active_processes, kill_all_processes, monitor_process_output
from lib.osc_bridge.router import OSCRouter
from pythonosc import udp_client

# Default settings
DEFAULT_PRESET = "00 - Simple Mono"
DEFAULT_OSC_PORT = 9000
DEFAULT_ROUTER_NAME = "router"
DEFAULT_UI_PORT = 9002
DEFAULT_PRESETS_DIR = "presets"

def kill_existing_processes():
    """Kill any existing Caelus processes."""
    LOG.info("Killing any existing Caelus processes")
    kill_all_processes()

def load_preset_config(preset_name: str) -> Dict[str, Any]:
    """
    Load the preset configuration from voices.yaml.
    
    Args:
        preset_name: Name of the preset to load
        
    Returns:
        Dictionary with preset info and configuration
    """
    bank_manager = BankManager(DEFAULT_PRESETS_DIR)
    return bank_manager.load_bank(preset_name)

def start_router(preset_config: Dict[str, Any], router_port: int = DEFAULT_OSC_PORT) -> Optional[OSCRouter]:
    """
    Start the OSC router with the given configuration.
    
    Args:
        preset_config: Dictionary with preset configuration
        router_port: Port to use for the router
        
    Returns:
        OSCRouter instance if successful, None otherwise
    """
    try:
        voices_cfg = preset_config['config']
        voices_file = os.path.join(preset_config['bank_dir'], 'voices.yaml')
        
        LOG.info(f"Starting OSC router with config from {voices_file}")
        
        # Create and start the router
        router = OSCRouter(config_file=voices_file, router_port=router_port)
        
        # Start router in background
        router.start_in_background()
        
        # Give router time to initialize
        LOG.info("Waiting for router to initialize...")
        time.sleep(4)
        
        return router
    except Exception as e:
        LOG.error(f"Failed to start router: {e}")
        return None

def launch_synths(preset_config: Dict[str, Any]) -> Dict[str, int]:
    """
    Launch synth processes based on the preset configuration.
    
    Args:
        preset_config: Dictionary with preset configuration
        
    Returns:
        Dictionary with counts of local and remote synths
    """
    synth_path = preset_config['synth_file']
    voices_cfg = preset_config['config']
    default_host = voices_cfg.get('settings', {}).get('synth_host', '127.0.0.1')
    
    LOG.info(f"Using synth binary: {synth_path}")
    
    local_count = 0
    remote_count = 0
    
    # Track which synths we've already processed
    processed_synths = set()
    
    for voice in voices_cfg.get('voices', []):
        host = voice.get('host', default_host)
        port = voice.get('port')
        vid = voice.get('id')
        
        # Skip duplicate port/host combinations
        synth_key = f"{host}:{port}"
        if synth_key in processed_synths:
            LOG.info(f"Skipping duplicate synth definition: {synth_key}")
            continue
        
        processed_synths.add(synth_key)
        
        if host in ('127.0.0.1', 'localhost'):
            # Launch local synth
            cmd = [synth_path, '-port', str(port)]
            LOG.info(f"Launching local synth {vid} on port {port}")
            
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                active_processes.append(proc)
                threading.Thread(
                    target=monitor_process_output,
                    args=(proc, f"synth_{vid}"),
                    daemon=True
                ).start()
                
                LOG.info(f"Synth process spawned with PID: {proc.pid}")
                local_count += 1
                time.sleep(1)  # Give each synth time to start up
            except Exception as e:
                LOG.error(f"Failed to spawn synth process: {e}")
                LOG.error(f"Command was: {' '.join(cmd)}")
        else:
            # Count remote synths
            remote_count += 1
    
    LOG.info(f"Launched {local_count} local and found {remote_count} remote synths")
    return {'local': local_count, 'remote': remote_count}

def verify_synth_connections(preset_config: Dict[str, Any], router_name: str = DEFAULT_ROUTER_NAME) -> bool:
    """
    Verify connections to synths by sending test messages.
    
    Args:
        preset_config: Dictionary with preset configuration
        router_name: Name of the router
        
    Returns:
        True if all connections were verified, False otherwise
    """
    voices_cfg = preset_config['config']
    default_host = voices_cfg.get('settings', {}).get('synth_host', '127.0.0.1')
    
    # Give synths time to fully start up
    LOG.info("Waiting for synths to initialize...")
    time.sleep(2)
    
    # Track success for each synth
    success_count = 0
    total_synths = 0
    
    # Test each unique synth
    processed_synths = set()
    
    for voice in voices_cfg.get('voices', []):
        host = voice.get('host', default_host)
        port = voice.get('port')
        vid = voice.get('id')
        
        # Skip duplicate port/host combinations
        synth_key = f"{host}:{port}"
        if synth_key in processed_synths:
            continue
        
        processed_synths.add(synth_key)
        total_synths += 1
        
        LOG.info(f"Testing connection to synth {vid} at {host}:{port}")
        
        # Create OSC client for this synth
        client = udp_client.SimpleUDPClient(host, port)
        
        # Try to send a test message
        try:
            # Send a harmless test message
            client.send_message("/ping", 1)
            LOG.info(f"Successfully sent test message to synth {vid}")
            success_count += 1
        except Exception as e:
            LOG.error(f"Failed to send test message to synth {vid}: {e}")
    
    # Check if all connections were successful
    if success_count == total_synths:
        LOG.info(f"All {success_count} synth connections verified")
        return True
    else:
        LOG.warning(f"Only {success_count}/{total_synths} synth connections verified")
        return False

def launch_gui(preset_name: str, router_port: int = DEFAULT_OSC_PORT, 
               ui_port: int = DEFAULT_UI_PORT, router_name: str = DEFAULT_ROUTER_NAME) -> bool:
    """
    Launch the Caelus GUI with the given preset.
    
    Args:
        preset_name: Name of the preset to use
        router_port: Port of the router
        ui_port: Port for UI feedback
        router_name: Name of the router
        
    Returns:
        True if GUI was launched successfully, False otherwise
    """
    try:
        LOG.info(f"Launching Caelus GUI with preset: {preset_name}")
        
        # Build command to launch main Caelus script
        cmd = [
            sys.executable,
            "caelus",
            "--default-bank", preset_name,
            "--router-port", str(router_port),
            "--ui-port", str(ui_port),
            "--router-name", router_name,
            "--no-auto-start-router"  # Important: don't start another router
        ]
        
        LOG.info(f"GUI command: {' '.join(cmd)}")
        
        # Launch GUI as separate process
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        active_processes.append(proc)
        threading.Thread(
            target=monitor_process_output,
            args=(proc, "CAELUS_GUI"),
            daemon=True
        ).start()
        
        LOG.info(f"GUI process spawned with PID: {proc.pid}")
        return True
    except Exception as e:
        LOG.error(f"Failed to launch GUI: {e}")
        return False

def main():
    """
    Main entry point for the router-first launcher.
    
    Process:
    1. Kill any existing processes
    2. Load preset config
    3. Start router
    4. Launch synths
    5. Verify synth connections
    6. Launch GUI
    """
    try:
        # 1. Kill existing processes
        kill_existing_processes()
        
        # Get preset name from command line or use default
        preset_name = DEFAULT_PRESET
        if len(sys.argv) > 1:
            preset_name = sys.argv[1]
        
        # 2. Load preset config
        LOG.info(f"Loading preset: {preset_name}")
        preset_config = load_preset_config(preset_name)
        
        # 3. Start router
        router = start_router(preset_config)
        if not router:
            LOG.error("Failed to start router, aborting")
            return 1
        
        # 4. Launch synths
        synth_counts = launch_synths(preset_config)
        if synth_counts['local'] + synth_counts['remote'] == 0:
            LOG.error("No synths were launched, aborting")
            return 1
        
        # 5. Verify synth connections
        connection_ok = verify_synth_connections(preset_config)
        if not connection_ok:
            LOG.warning("Some synth connections could not be verified")
            # Continue anyway, as some connections might still work
        
        # 6. Launch GUI
        gui_launched = launch_gui(preset_name)
        if not gui_launched:
            LOG.error("Failed to launch GUI")
            return 1
        
        # Keep the script running until interrupted
        try:
            LOG.info("Caelus started successfully. Press Ctrl+C to exit.")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            LOG.info("Shutting down Caelus")
            kill_existing_processes()
        
        return 0
    except Exception as e:
        LOG.error(f"Error in launcher: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 
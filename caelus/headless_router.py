#!/usr/bin/env python3
"""
Headless OSC Router for Caelus

A simple script that:
1. Starts the OSC router
2. Loads synths from voices.yaml
3. Keeps running in headless mode (no GUI)
"""
import os
import sys
import time
import signal
import subprocess
import threading
import atexit
import socket
from typing import Optional, List, Dict, Any

from lib.common.utils import LOG
from lib.midi_osc.helpers import kill_all_processes, active_processes, monitor_process_output
from lib.osc_bridge.router import OSCRouter
from lib.common.bank_manager import BankManager

# Default settings
DEFAULT_PRESET = "00 - Simple Mono"
DEFAULT_ROUTER_PORT = 9000
DEFAULT_PRESETS_DIR = "presets"

# Global router instance for cleanup
router = None
synth_pids = []
cleanup_done = False  # Flag to prevent multiple cleanups

def is_port_in_use(port, host='0.0.0.0'):
    """Check if a port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.bind((host, port))
            return False
        except socket.error:
            return True

def find_synth_processes():
    """Find all running synth processes."""
    try:
        # Look for processes with 'synth' in the command line
        result = subprocess.run(
            ["ps", "-ef"],
            capture_output=True,
            text=True,
            check=True
        )
        
        found_pids = []
        for line in result.stdout.splitlines():
            if "presets" in line and "synth" in line and "python" not in line:
                # Extract PID from ps output (second column)
                parts = line.split()
                if len(parts) > 2:
                    try:
                        pid = int(parts[1])
                        found_pids.append(pid)
                    except ValueError:
                        pass
        
        return found_pids
    except Exception as e:
        LOG.error(f"Error finding synth processes: {e}")
        return []

def kill_all_synths():
    """Forcibly kill all synth processes."""
    global synth_pids, cleanup_done
    
    # Only run cleanup once
    if cleanup_done:
        return
        
    cleanup_done = True
    
    # First try to kill child processes tracked by active_processes
    LOG.info("Killing tracked child processes...")
    kill_all_processes()
    
    # Then find and kill any remaining synth processes
    remaining_pids = find_synth_processes()
    all_pids = set(synth_pids + remaining_pids)
    
    if all_pids:
        LOG.info(f"Killing {len(all_pids)} synth processes: {all_pids}")
        for pid in all_pids:
            try:
                LOG.info(f"Sending SIGTERM to PID {pid}")
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            except Exception as e:
                LOG.error(f"Error killing process {pid}: {e}")
        
        # Give processes time to terminate
        time.sleep(0.5)
        
        # Force kill any remaining processes
        for pid in all_pids:
            try:
                # Check if process still exists
                os.kill(pid, 0)  # Signal 0 doesn't kill but checks existence
                LOG.info(f"Process {pid} still alive, sending SIGKILL")
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except Exception:
                pass
    
    LOG.info("All synth processes killed")

def signal_handler(sig, frame):
    """Handle SIGINT (Ctrl+C) to clean up before exiting."""
    LOG.info("Shutting down...")
    kill_all_synths()
    sys.exit(0)

def launch_synths(synth_path: str, voices_config: Dict[str, Any]) -> int:
    """
    Launch synth processes for each voice in the config.
    
    Args:
        synth_path: Path to the synth binary
        voices_config: Voices configuration from voices.yaml
        
    Returns:
        Number of synths launched
    """
    global synth_pids
    count = 0
    default_host = voices_config.get('settings', {}).get('synth_host', '127.0.0.1')
    
    # Track which synths we've already processed to avoid duplicates
    processed_synths = set()
    
    for voice in voices_config.get('voices', []):
        host = voice.get('host', default_host)
        port = voice.get('port')
        vid = voice.get('id')
        
        # Skip remote synths
        if host not in ('127.0.0.1', 'localhost'):
            LOG.info(f"Skipping remote synth {vid} at {host}:{port}")
            continue
            
        # Skip duplicate port/host combinations
        synth_key = f"{host}:{port}"
        if synth_key in processed_synths:
            LOG.info(f"Skipping duplicate synth definition: {synth_key}")
            continue
            
        processed_synths.add(synth_key)
        
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
            synth_pids.append(proc.pid)
            
            threading.Thread(
                target=monitor_process_output,
                args=(proc, f"synth_{vid}"),
                daemon=True
            ).start()
            
            LOG.info(f"Synth process {vid} spawned with PID: {proc.pid}")
            count += 1
            time.sleep(1)  # Give each synth time to start up
        except Exception as e:
            LOG.error(f"Failed to spawn synth process {vid}: {e}")
            LOG.error(f"Command was: {' '.join(cmd)}")
    
    return count

def main():
    """Start OSC router and synths in headless mode."""
    global router
    
    # Register signal handler for clean shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Register exit handler to ensure cleanup
    atexit.register(kill_all_synths)
    
    # Parse command line arguments
    preset_name = DEFAULT_PRESET
    if len(sys.argv) > 1:
        preset_name = sys.argv[1]
    
    router_port = DEFAULT_ROUTER_PORT
    if len(sys.argv) > 2:
        try:
            router_port = int(sys.argv[2])
        except ValueError:
            LOG.error(f"Invalid port number: {sys.argv[2]}")
            return 1
    
    # Check if OSC router port is already in use
    if is_port_in_use(router_port):
        LOG.error(f"Port {router_port} is already in use.")
        LOG.error("Either stop the other application using this port or specify a different port.")
        LOG.error("Usage: ./headless_router.py [preset_name] [router_port]")
        return 1
    
    # Kill any existing processes
    LOG.info("Killing any existing Caelus processes")
    kill_all_synths()
    
    # Reset cleanup flag after initial cleanup
    global cleanup_done
    cleanup_done = False
    
    # Load preset config
    LOG.info(f"Loading preset: {preset_name}")
    try:
        bank_manager = BankManager(DEFAULT_PRESETS_DIR)
        preset_config = bank_manager.load_bank(preset_name)
        
        bank_dir = preset_config['bank_dir']
        voices_file = os.path.join(bank_dir, 'voices.yaml')
        synth_path = preset_config['synth_file']
        
        LOG.info(f"Using synth binary: {synth_path}")
        LOG.info(f"Using voices config: {voices_file}")
        
        # Launch synth processes first
        LOG.info("Launching synth processes...")
        synth_count = launch_synths(synth_path, preset_config['config'])
        LOG.info(f"Launched {synth_count} synth processes")
        
        # Give synths time to start up
        LOG.info("Waiting for synths to initialize...")
        time.sleep(2)
        
        # Start router with the voices config
        LOG.info(f"Starting OSC router on port {router_port}")
        router = OSCRouter(config_file=voices_file, router_port=router_port)
        
        # Ensure the config has been loaded
        if not hasattr(router, 'voice_manager') or len(router.voice_manager.voices) == 0:
            LOG.error("No voices configured in the router")
            kill_all_synths()
            return 1
        
        # Start the router
        LOG.info("Starting router in blocking mode")
        LOG.info(f"Configured with {len(router.voice_manager.voices)} voices")
        
        # Print voice details
        for i, voice in enumerate(router.voice_manager.voices):
            LOG.info(f"Voice {i}: {voice.id} on {voice.host}:{voice.port}")
        
        try:
            # Start the router and block
            router.run()  # This will block until the router is stopped
        except KeyboardInterrupt:
            LOG.info("Router stopped by keyboard interrupt")
        except Exception as e:
            LOG.error(f"Router error: {e}")
        finally:
            LOG.info("Router shutting down, cleaning up synth processes...")
            kill_all_synths()
        
        return 0
    except Exception as e:
        LOG.error(f"Error starting headless router: {e}")
        import traceback
        traceback.print_exc()
        kill_all_synths()
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        # Final cleanup in case of unexpected exit
        kill_all_synths() 
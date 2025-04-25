"""
Helper functions for the MIDI-OSC bridge
"""
import subprocess
from lib.core.utils import LOG

# Process management
active_processes = []

def kill_process(proc):
    """Terminate or kill a subprocess"""
    if proc and proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
        except Exception as e:
            LOG.error(f"Error killing process: {e}")

def kill_all_processes():
    """Kill all child processes"""
    LOG.info(f"Killing {len(active_processes)} child processes")
    
    # First try gentle termination
    for proc in active_processes[:]:  # Make a copy to avoid modification during iteration
        try:
            LOG.info(f"Terminating process {proc.pid}")
            proc.terminate()
            # Wait a short time for process to terminate
            proc.wait(timeout=0.5)
        except Exception as e:
            LOG.error(f"Error terminating process: {e}")
    
    # Check if any processes are still running and kill them forcefully
    import time
    time.sleep(0.5)  # Give processes time to shutdown
    
    remaining = [p for p in active_processes if p.poll() is None]
    if remaining:
        LOG.warning(f"{len(remaining)} processes still running after terminate, forcing kill")
        import signal
        import os
        
        for proc in remaining:
            try:
                LOG.info(f"Force killing process {proc.pid}")
                os.kill(proc.pid, signal.SIGKILL)
            except Exception as e:
                LOG.error(f"Error force killing process: {e}")
    
    # Clear the process list
    active_processes.clear()
    LOG.info("All processes killed")
    return True

def monitor_process_output(proc, name):
    """Monitor the stdout and stderr of a process"""
    while proc.poll() is None:
        stdout_line = proc.stdout.readline()
        if stdout_line:
            LOG.info(f"{name} STDOUT: {stdout_line.rstrip()}")
        stderr_line = proc.stderr.readline()
        if stderr_line:
            LOG.error(f"{name} STDERR: {stderr_line.rstrip()}")
    LOG.info(f"Process {name} exited with code {proc.returncode}")

def send_osc(osc_client, address, value):
    """Send an OSC message and log it"""
    if osc_client is None:
        LOG.error("OSC client is None, cannot send message")
        return False
        
    try:
        # Log before sending in case the send causes a crash
        LOG.info(f"Preparing to send OSC: {address} {value}")
        
        # Validate input types
        if not isinstance(address, str):
            LOG.error(f"Invalid OSC address type: {type(address)}")
            return False
            
        # Make sure method exists
        if not hasattr(osc_client, 'send_message'):
            LOG.error(f"OSC client does not have send_message method")
            return False
            
        # Ensure we're sending properly typed values
        # If value is a list, ensure all elements are properly typed
        if isinstance(value, list):
            # Make a copy to avoid modifying the original
            processed_value = []
            for item in value:
                # Convert booleans to integers (0/1)
                if isinstance(item, bool):
                    processed_value.append(1 if item else 0)
                # Ensure numbers are proper floats for OSC
                elif isinstance(item, (int, float)):
                    processed_value.append(float(item))
                else:
                    processed_value.append(item)
            value = processed_value
        # Handle single values as well
        elif isinstance(value, bool):
            value = 1 if value else 0
            
        # Send the message with a proper try/except
        osc_client.send_message(address, value)
        LOG.info(f"OSC message sent successfully: {address}")
        return True
    except Exception as e:
        LOG.error(f"ERROR sending OSC message to {address}: {e}")
        import traceback
        traceback.print_exc()
        return False 
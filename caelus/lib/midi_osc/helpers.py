"""
Helper functions for the MIDI-OSC bridge
"""
import subprocess
from lib.common.utils import LOG

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

def set_light(label, on):
    """Set a GUI indicator light on or off"""
    color = "#FFA500" if on else "#333"
    label.setStyleSheet(f"""
        background-color: {color};
        border-radius: 15px;
        border: 2px solid #FFA500;
    """)
    label.repaint()

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
    try:
        LOG.info(f"Sending OSC: {address} {value}")
        osc_client.send_message(address, value)
        return True
    except Exception as e:
        LOG.error(f"ERROR sending OSC message: {e}")
        return False 
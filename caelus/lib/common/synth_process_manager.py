"""
SynthProcessManager - Manages launching and tracking of OSC router and synth subprocesses.
"""
import threading
import subprocess
from typing import List, Optional
from lib.midi_osc.helpers import active_processes, kill_all_processes, monitor_process_output

class SynthProcessManager:
    """
    Provides methods to spawn and track synth and router processes,
    and to kill them all when needed.
    """
    def __init__(self) -> None:
        """Initialize the process manager (uses shared active_processes list)."""
        # active_processes is imported from helpers
        pass

    def kill_all(self) -> bool:
        """
        Terminate all spawned synth and router processes.

        Returns:
            True if processes were successfully killed.
        """
        return kill_all_processes()

    def spawn_router(self, cmd: List[str], name: str = "OSC ROUTER") -> Optional[subprocess.Popen]:
        """
        Spawn the OSC router subprocess in text mode with stdout/stderr captured.

        Args:
            cmd: Command list to launch the router
            name: Label for logging the process output

        Returns:
            The subprocess.Popen instance, or None on error.
        """
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )
            active_processes.append(proc)
            threading.Thread(
                target=monitor_process_output,
                args=(proc, name),
                daemon=True
            ).start()
            return proc
        except Exception:
            return None

    def spawn_synth(self, cmd: List[str], name: str) -> Optional[subprocess.Popen]:
        """
        Spawn a local synth subprocess with stdout/stderr captured.

        Args:
            cmd: Command list to launch the synth binary
            name: Label for logging the process output

        Returns:
            The subprocess.Popen instance, or None on error.
        """
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            active_processes.append(proc)
            threading.Thread(
                target=monitor_process_output,
                args=(proc, name),
                daemon=True
            ).start()
            return proc
        except Exception:
            return None 
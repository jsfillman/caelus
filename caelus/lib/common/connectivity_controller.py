"""
ConnectivityController - Tracks active synth/router processes and reports connection status.
"""
from PyQt6.QtCore import QObject, pyqtSignal
from lib.midi_osc.helpers import active_processes

class ConnectivityController(QObject):
    """
    Provides methods to check how many child processes are running and alive.
    """
    # Emitted when connectivity changes: (alive_count, total_count)
    connectivity_changed = pyqtSignal(int, int)

    def __init__(self, poll_interval_ms: int = 1000) -> None:
        super().__init__()
        self.poll_interval_ms = poll_interval_ms

    def total_count(self) -> int:
        """Return total number of managed subprocesses."""
        return len(active_processes)

    def alive_count(self) -> int:
        """Return number of alive (still running) subprocesses."""
        return sum(1 for p in active_processes if p.poll() is None)

    def check_connectivity(self) -> None:
        """Emit current connectivity status."""
        total = self.total_count()
        alive = self.alive_count()
        self.connectivity_changed.emit(alive, total) 
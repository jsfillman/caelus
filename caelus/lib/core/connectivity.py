"""
Connectivity monitoring for Caelus.

This module provides process monitoring and connectivity checking for synth processes.
"""
import time
from typing import List, Dict, Any, Optional, Callable
import subprocess
from PyQt6.QtCore import QTimer, QObject, pyqtSignal as Signal

from lib.core.utils import LOG

class ConnectivityMonitor(QObject):
    """Monitor for checking and reporting synth process connectivity."""
    
    # Signal emitted when connectivity status changes
    connectivity_changed = Signal(int, int)  # (alive_count, total_count)
    
    def __init__(self, check_interval: int = 30000):
        """
        Initialize the connectivity monitor.
        
        Args:
            check_interval: Interval between connectivity checks in milliseconds
        """
        super().__init__()
        self.check_interval = check_interval
        self.timer: Optional[QTimer] = None
        self.processes: List[subprocess.Popen] = []
        self.callback: Optional[Callable[[int, int], None]] = None
    
    def start_monitoring(self, 
                        processes: Optional[List[subprocess.Popen]] = None,
                        callback: Optional[Callable[[int, int], None]] = None) -> None:
        """
        Start monitoring synth process connectivity.
        
        Args:
            processes: List of subprocess.Popen objects to monitor
            callback: Optional callback function for connectivity status updates
        """
        if processes:
            self.processes = processes
            
        if callback:
            self.callback = callback
            
        # Setup timer for periodic connectivity checks
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_connectivity)
        self.timer.start(self.check_interval)
        
        # Initial connectivity check
        self.check_connectivity()
        
    def stop_monitoring(self) -> None:
        """Stop monitoring synth process connectivity."""
        if self.timer:
            self.timer.stop()
            self.timer = None
    
    def update_processes(self, processes: List[subprocess.Popen]) -> None:
        """
        Update the list of processes to monitor.
        
        Args:
            processes: New list of processes to monitor
        """
        self.processes = processes
        
        # Run an immediate connectivity check
        self.check_connectivity()
    
    def check_connectivity(self) -> None:
        """Check if all synth voices are connected and emit status updates."""
        if not self.processes:
            return
            
        # Count alive processes
        total_count = len(self.processes)
        alive_count = sum(1 for p in self.processes if p.poll() is None)
        
        LOG.info(f"Synth connectivity check: {alive_count}/{total_count} synths connected")
        
        # Emit signal with connectivity status
        self.connectivity_changed.emit(alive_count, total_count)
        
        # If callback is set, call it with connectivity status
        if self.callback:
            self.callback(alive_count, total_count)
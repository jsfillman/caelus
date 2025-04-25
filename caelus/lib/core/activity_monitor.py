"""
Activity monitor for Caelus.

This module provides a class for monitoring and coordinating activity indicators.
"""
from typing import Dict, Optional, Callable
from PyQt6.QtCore import QObject, QTimer, pyqtSignal as Signal

from lib.common.utils import LOG

class ActivityMonitor(QObject):
    """
    Monitor for tracking activity in various components.
    
    Coordinates the flashing and timing of activity indicators to provide
    visual feedback for MIDI, OSC, and other activities.
    """
    
    # Signals for activity updates
    midi_activity = Signal(bool)  # (active)
    osc_activity = Signal(bool)   # (active)
    
    def __init__(self, flash_interval: int = 100):
        """
        Initialize the activity monitor.
        
        Args:
            flash_interval: Time in milliseconds for activity indicator flashing
        """
        super().__init__()
        
        # Store parameters
        self.flash_interval = flash_interval
        
        # Initialize activity state
        self.activity_state = {
            "midi": False,
            "osc": False
        }
        
        # Initialize recent activity flags
        self.recent_activity = {
            "midi": False,
            "osc": False
        }
        
        # Create timer for auto-dimming
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._check_activity)
        self.timer.start(self.flash_interval)
    
    def register_midi_activity(self) -> None:
        """Register MIDI activity, triggering indicator."""
        self.recent_activity["midi"] = True
        
        # Only emit if state is changing
        if not self.activity_state["midi"]:
            self.activity_state["midi"] = True
            self.midi_activity.emit(True)
    
    def register_osc_activity(self) -> None:
        """Register OSC activity, triggering indicator."""
        self.recent_activity["osc"] = True
        
        # Only emit if state is changing
        if not self.activity_state["osc"]:
            self.activity_state["osc"] = True
            self.osc_activity.emit(True)
    
    def _check_activity(self) -> None:
        """Check for recent activity and dim indicators if inactive."""
        # Check MIDI activity
        if not self.recent_activity["midi"] and self.activity_state["midi"]:
            self.activity_state["midi"] = False
            self.midi_activity.emit(False)
            
        # Check OSC activity
        if not self.recent_activity["osc"] and self.activity_state["osc"]:
            self.activity_state["osc"] = False
            self.osc_activity.emit(False)
            
        # Reset recent activity flags
        self.recent_activity["midi"] = False
        self.recent_activity["osc"] = False
    
    def start(self) -> None:
        """Start the activity monitor."""
        if not self.timer.isActive():
            self.timer.start(self.flash_interval)
            LOG.info("Activity monitor started")
    
    def stop(self) -> None:
        """Stop the activity monitor."""
        if self.timer.isActive():
            self.timer.stop()
            LOG.info("Activity monitor stopped")
            
            # Turn off all indicators
            self.midi_activity.emit(False)
            self.osc_activity.emit(False)
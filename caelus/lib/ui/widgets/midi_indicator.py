"""
MIDI activity indicator widget for Caelus.

This module provides a reusable indicator light for MIDI activity.
"""
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QLabel, QHBoxLayout, QVBoxLayout, QFrame
)
from PyQt6.QtCore import Qt, QTimer

class MidiIndicator(QWidget):
    """
    A MIDI activity indicator light with label.
    
    Features:
    - Visual indicator that lights up on MIDI activity
    - Auto-dimming after a short delay
    - Customizable color and label
    """
    
    def __init__(
        self,
        label: str = "MIDI",
        active_color: str = "#FFA500",
        inactive_color: str = "#333333",
        timeout: int = 100,
        size: int = 30,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize the MIDI activity indicator.
        
        Args:
            label: Text label for the indicator
            active_color: Color to use when the indicator is active (CSS color string)
            inactive_color: Color to use when the indicator is inactive (CSS color string)
            timeout: Time in milliseconds before automatically dimming the indicator
            size: Size of the indicator light in pixels
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.label_text = label
        self.active_color = active_color
        self.inactive_color = inactive_color
        self.timeout = timeout
        self.size = size
        
        # Initialize state
        self.is_active = False
        self.recent_activity = False
        
        # Set up UI
        self._setup_ui()
        
        # Timer for auto-dimming
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._dim_light)
        self.timer.start(self.timeout)
    
    def _setup_ui(self) -> None:
        """Set up the user interface layout and widgets."""
        # Main layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        
        # Text label
        self.label = QLabel(self.label_text)
        self.label.setStyleSheet("font-size: 12px; color: #CCCCCC;")
        layout.addWidget(self.label)
        
        # Indicator light
        self.light = QLabel()
        self.light.setFixedSize(self.size, self.size)
        self.light.setFrameShape(QFrame.Shape.NoFrame)
        self._update_light_style(False)
        layout.addWidget(self.light)
        
    def _update_light_style(self, active: bool) -> None:
        """
        Update the indicator light style based on activity state.
        
        Args:
            active: Whether the light should be active
        """
        color = self.active_color if active else self.inactive_color
        self.light.setStyleSheet(f"""
            background-color: {color};
            border-radius: {self.size // 2}px;
            border: 2px solid {self.active_color};
        """)
        self.is_active = active
    
    def set_active(self, active: bool = True) -> None:
        """
        Set the activity state of the indicator.
        
        Args:
            active: Whether the indicator should be active
        """
        self._update_light_style(active)
        self.recent_activity = active
    
    def flash(self) -> None:
        """Flash the indicator light briefly."""
        self.set_active(True)
        
    def _dim_light(self) -> None:
        """Turn off the indicator light after a delay if no recent activity."""
        if not self.recent_activity and self.is_active:
            self._update_light_style(False)
        self.recent_activity = False
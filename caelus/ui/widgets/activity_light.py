"""
Activity light widget for Caelus.

This module provides a reusable visual indicator for activity.
"""
from typing import Optional
from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout, QFrame
from PyQt6.QtCore import QTimer

class ActivityLight(QWidget):
    """
    A customizable activity indicator light with label.
    
    Features:
    - Visual indicator that lights up on activity
    - Auto-dimming after a short delay
    - Customizable color, label and timeout
    """
    
    def __init__(
        self,
        label: str = "Activity",
        active_color: str = "#FFA500",  # Orange
        inactive_color: str = "#333333",  # Dark gray
        timeout: int = 100,  # ms
        size: int = 30,  # px
        parent: Optional[QWidget] = None
    ):
        """
        Initialize the activity light.
        
        Args:
            label: Text label for the indicator
            active_color: Color to use when active (CSS color string)
            inactive_color: Color to use when inactive (CSS color string)
            timeout: Time in milliseconds before automatically dimming
            size: Size of the indicator light in pixels
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Store configuration
        self.label_text = label
        self.active_color = active_color
        self.inactive_color = inactive_color
        self.timeout = timeout
        self.size = size
        
        # Initialize state
        self.is_active = False
        self.recent_activity = False
        
        # Set up the UI
        self._setup_ui()
        
        # Create timer for auto-dimming
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._dim_light)
        self.timer.start(self.timeout)
    
    def _setup_ui(self) -> None:
        """Set up the user interface layout and widgets."""
        # Create layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        
        # Add label
        self.label = QLabel(self.label_text)
        self.label.setStyleSheet("font-size: 12px; color: #CCCCCC;")
        layout.addWidget(self.label)
        
        # Create light indicator
        self.light = QLabel()
        self.light.setFixedSize(self.size, self.size)
        self.light.setFrameShape(QFrame.Shape.NoFrame)
        
        # Set initial light state (inactive)
        self._update_light_style(False)
        
        # Add light to layout
        layout.addWidget(self.light)
        
    def _update_light_style(self, active: bool) -> None:
        """
        Update the light's visual style based on activity state.
        
        Args:
            active: Whether the light should be shown as active
        """
        # Choose color based on state
        color = self.active_color if active else self.inactive_color
        
        # Apply CSS styling
        self.light.setStyleSheet(f"""
            background-color: {color};
            border-radius: {self.size // 2}px;
            border: 2px solid {self.active_color};
        """)
        
        # Update state
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
        """Turn off the indicator light if no recent activity."""
        if not self.recent_activity and self.is_active:
            self._update_light_style(False)
        self.recent_activity = False
        
    def set_label(self, text: str) -> None:
        """
        Update the label text.
        
        Args:
            text: New label text
        """
        self.label_text = text
        self.label.setText(text)
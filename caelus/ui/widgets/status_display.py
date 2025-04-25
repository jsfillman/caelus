"""
Status display widget for Caelus.

This module provides a reusable status display for showing text messages with color-coding.
"""
from typing import Optional, Dict
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QFrame
from PyQt6.QtCore import Qt

class StatusDisplay(QWidget):
    """
    A customizable status display widget for showing status messages.
    
    Features:
    - Color-coded status messages
    - Support for different status types (info, warning, error)
    - Customizable styling
    """
    
    # Default colors for status types
    DEFAULT_COLORS = {
        "info": "#00FF00",      # Green
        "warning": "#FFAA00",   # Orange
        "error": "#FF0000",     # Red
        "note": "#00AAFF",      # Light blue
        "default": "#FFFFFF"    # White
    }
    
    def __init__(
        self,
        initial_text: str = "Ready",
        initial_color: str = "#00FF00",
        font_size: int = 14,
        colors: Optional[Dict[str, str]] = None,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize the status display.
        
        Args:
            initial_text: Initial status text to display
            initial_color: Initial text color (CSS color string)
            font_size: Font size in pixels
            colors: Optional dict of status type to color mappings
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Store configuration
        self.font_size = font_size
        self.colors = colors or self.DEFAULT_COLORS.copy()
        
        # Set up the UI
        self._setup_ui()
        
        # Set initial status
        self.set_status(initial_text, initial_color)
    
    def _setup_ui(self) -> None:
        """Set up the user interface layout and widgets."""
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Create frame for styling
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet("""
            QFrame {
                background-color: #222222;
                border: 1px solid #444444;
                border-radius: 5px;
                padding: 5px;
            }
        """)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(10, 5, 10, 5)
        
        # Create status label
        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        frame_layout.addWidget(self.status_label)
        
        # Add frame to main layout
        layout.addWidget(frame)
    
    def set_status(self, text: str, color: str) -> None:
        """
        Set the status display text and color.
        
        Args:
            text: Status text to display
            color: Text color (CSS color string)
        """
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color}; font-size: {self.font_size}px;")
    
    def update_status(self, status_type: str, message: str) -> None:
        """
        Update status based on status type and message.
        
        Args:
            status_type: Status type (info, warning, error, note)
            message: Status message to display
        """
        # Get color for status type or use default
        color = self.colors.get(status_type, self.colors["default"])
        
        # Update display
        self.set_status(message, color)
    
    def set_font_size(self, size: int) -> None:
        """
        Set the font size.
        
        Args:
            size: Font size in pixels
        """
        self.font_size = size
        
        # Update the display with current text and color
        current_text = self.status_label.text()
        current_color = self.status_label.styleSheet().split(';')[0].split(':')[1].strip()
        self.set_status(current_text, current_color)
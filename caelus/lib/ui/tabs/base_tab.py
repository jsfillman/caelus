"""
Base tab class for Caelus.

This module provides a base class for all tab widgets.
"""
from typing import Dict, Any, Optional, List

from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import pyqtSignal as Signal

class BaseTab(QWidget):
    """
    Base class for all tab widgets.
    
    Features:
    - Common tab interface and functionality
    - Standard layout setup
    - Signal handling for tab events
    """
    
    # Signal emitted when tab is activated
    tab_activated = Signal()
    
    # Signal emitted when tab is deactivated
    tab_deactivated = Signal()
    
    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize the base tab.
        
        Args:
            parent: Parent widget
        """
        # Initialize QWidget
        super().__init__(parent)
        
        # Common properties
        self.tab_name = "Base Tab"
        self.is_active = False
        
        # Set up UI
        self._setup_ui()
        
    def _setup_ui(self) -> None:
        """Set up the user interface layout and widgets."""
        # Create the layout with a different name to avoid method/attribute confusion
        self.layout_obj = QVBoxLayout(self)
        self.layout_obj.setContentsMargins(10, 10, 10, 10)
        self.layout_obj.setSpacing(10)
        
    def on_tab_activated(self) -> None:
        """Handle tab activation events."""
        self.is_active = True
        self.tab_activated.emit()
        
    def on_tab_deactivated(self) -> None:
        """Handle tab deactivation events."""
        self.is_active = False
        self.tab_deactivated.emit()
        
    def reset(self) -> None:
        """Reset the tab to its default state."""
        pass
        
    def update_parameters(self, parameters: Dict[str, Any]) -> None:
        """
        Update parameter values displayed in the tab.
        
        Args:
            parameters: Dictionary of parameter names and values
        """
        pass
        
    def get_tab_name(self) -> str:
        """
        Get the display name for this tab.
        
        Returns:
            Tab display name
        """
        return self.tab_name
        
    def set_tab_name(self, name: str) -> None:
        """
        Set the display name for this tab.
        
        Args:
            name: New tab name
        """
        self.tab_name = name
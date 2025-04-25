"""
Parameter group widget for Caelus.

This module provides a container for grouping related parameters.
"""
from typing import List, Dict, Optional, Callable, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout
)
from PyQt6.QtCore import Qt, pyqtSignal as Signal

from .parameter_dial import ParameterDial

class ParameterGroup(QWidget):
    """
    A container for grouping related parameter controls.
    
    Features:
    - Title for the parameter group
    - Grid layout for organizing parameter dials
    - Visual styling for separation
    - Forwarded signals from child parameters
    """
    
    # Signal emitted when any child parameter value changes
    parameter_changed = Signal(str, float)  # (param_name, value)
    
    def __init__(
        self,
        title: str,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize the parameter group widget.
        
        Args:
            title: Group title
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.title = title
        self.parameters: Dict[str, ParameterDial] = {}
        
        # Set up UI
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the user interface layout and widgets."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)
        
        # Title
        self.title_label = QLabel(self.title)
        self.title_label.setStyleSheet("font-size: 14px; color: #FFAA00; font-weight: bold;")
        layout.addWidget(self.title_label)
        
        # Frame for parameters
        self.frame = QFrame()
        self.frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.frame.setStyleSheet("""
            QFrame {
                background-color: #222222;
                border: 1px solid #444444;
                border-radius: 5px;
            }
        """)
        
        # Grid layout for parameters
        self.grid_layout = QGridLayout(self.frame)
        self.grid_layout.setContentsMargins(5, 5, 5, 5)
        self.grid_layout.setSpacing(5)
        
        layout.addWidget(self.frame)
    
    def add_parameter(
        self,
        row: int,
        column: int,
        name: str,
        label: str,
        min_value: float = 0.0,
        max_value: float = 1.0,
        default_value: float = 0.5,
        step_size: float = 0.01,
        formatter: Optional[Callable[[float], str]] = None
    ) -> ParameterDial:
        """
        Add a parameter dial to the group.
        
        Args:
            row: Grid row position
            column: Grid column position
            name: Parameter name
            label: Parameter label
            min_value: Minimum parameter value
            max_value: Maximum parameter value
            default_value: Default parameter value
            step_size: Step size for parameter adjustments
            formatter: Value formatter function
            
        Returns:
            Created parameter dial widget
        """
        param = ParameterDial(
            name=name,
            label=label,
            min_value=min_value,
            max_value=max_value,
            default_value=default_value,
            step_size=step_size,
            formatter=formatter
        )
        
        # Connect the parameter's signal to forward it
        param.value_changed.connect(self._forward_parameter_change)
        
        # Add to grid layout
        self.grid_layout.addWidget(param, row, column)
        
        # Store parameter for later access
        self.parameters[name] = param
        
        return param
    
    def _forward_parameter_change(self, name: str, value: float) -> None:
        """
        Forward parameter change signals from child widgets.
        
        Args:
            name: Parameter name
            value: Parameter value
        """
        self.parameter_changed.emit(name, value)
    
    def set_parameter_value(self, name: str, value: float) -> None:
        """
        Set a parameter value by name.
        
        Args:
            name: Parameter name
            value: Value to set
        """
        if name in self.parameters:
            self.parameters[name].set_value(value)
    
    def get_parameter_value(self, name: str) -> Optional[float]:
        """
        Get a parameter value by name.
        
        Args:
            name: Parameter name
            
        Returns:
            Parameter value or None if parameter not found
        """
        if name in self.parameters:
            return self.parameters[name].get_value()
        return None
    
    def get_all_values(self) -> Dict[str, float]:
        """
        Get all parameter values.
        
        Returns:
            Dictionary of parameter names and values
        """
        return {name: param.get_value() for name, param in self.parameters.items()}
"""
Parameter dial widget for Caelus.

This module provides a reusable dial widget with label and value display.
"""
from typing import Callable, Optional, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QDial, QHBoxLayout, 
    QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal as Signal

class ParameterDial(QWidget):
    """
    A customizable parameter dial widget with label and value display.
    
    Features:
    - Dial control for parameter adjustment
    - Label for parameter name
    - Value display that updates as dial is turned
    - Optional value formatter for custom display
    - Signal for value changes
    """
    
    # Signal emitted when the parameter value changes
    value_changed = Signal(str, float)  # (param_name, value)
    
    def __init__(
        self, 
        name: str, 
        label: str,
        min_value: float = 0.0,
        max_value: float = 1.0,
        default_value: float = 0.5,
        step_size: float = 0.01,
        formatter: Optional[Callable[[float], str]] = None,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize the parameter dial widget.
        
        Args:
            name: Internal parameter name (used for signals)
            label: Display label for the parameter
            min_value: Minimum parameter value
            max_value: Maximum parameter value
            default_value: Default parameter value
            step_size: Step size for parameter adjustments
            formatter: Function to format the value for display
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.name = name
        self.label_text = label
        self.min_value = min_value
        self.max_value = max_value
        self.default_value = default_value
        self.step_size = step_size
        self.formatter = formatter or self._default_formatter
        
        # Calculate dial range
        self.range = int((max_value - min_value) / step_size)
        
        # Set up the UI
        self._setup_ui()
        
        # Set the initial value
        self.set_value(default_value)
    
    def _setup_ui(self) -> None:
        """Set up the user interface layout and widgets."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)
        
        # Parameter label
        self.label = QLabel(self.label_text)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("font-size: 12px; color: #CCCCCC;")
        layout.addWidget(self.label)
        
        # Dial
        self.dial = QDial()
        self.dial.setMinimum(0)
        self.dial.setMaximum(self.range)
        self.dial.setSingleStep(1)
        self.dial.setNotchesVisible(True)
        self.dial.setWrapping(False)
        self.dial.valueChanged.connect(self._on_dial_value_changed)
        
        # Make the dial a reasonable size
        self.dial.setMinimumSize(60, 60)
        self.dial.setMaximumSize(80, 80)
        
        # Center the dial
        dial_container = QHBoxLayout()
        dial_container.addStretch()
        dial_container.addWidget(self.dial)
        dial_container.addStretch()
        layout.addLayout(dial_container)
        
        # Value display
        self.value_label = QLabel("0.0")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_label.setStyleSheet("font-size: 12px; color: #FFAA00; font-weight: bold;")
        layout.addWidget(self.value_label)
        
        # Set widget size policy
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setMinimumSize(100, 100)
        self.setMaximumSize(120, 120)
    
    def _on_dial_value_changed(self, dial_value: int) -> None:
        """
        Handle dial value changes and convert to parameter values.
        
        Args:
            dial_value: Raw dial value (integer)
        """
        # Convert dial value to parameter value
        param_value = self._dial_to_param(dial_value)
        
        # Update the value display
        display_value = self.formatter(param_value)
        self.value_label.setText(display_value)
        
        # Emit the value changed signal
        self.value_changed.emit(self.name, param_value)
    
    def _dial_to_param(self, dial_value: int) -> float:
        """
        Convert a dial value to a parameter value.
        
        Args:
            dial_value: Raw dial value (integer)
            
        Returns:
            Corresponding parameter value
        """
        # Linear mapping from dial range to parameter range
        normalized = dial_value / self.range
        param_value = self.min_value + normalized * (self.max_value - self.min_value)
        
        # Round to step size precision
        steps = round(param_value / self.step_size)
        param_value = steps * self.step_size
        
        return param_value
    
    def _param_to_dial(self, param_value: float) -> int:
        """
        Convert a parameter value to a dial value.
        
        Args:
            param_value: Parameter value
            
        Returns:
            Corresponding dial value (integer)
        """
        # Ensure value is within range
        clamped_value = max(self.min_value, min(self.max_value, param_value))
        
        # Linear mapping from parameter range to dial range
        normalized = (clamped_value - self.min_value) / (self.max_value - self.min_value)
        dial_value = int(round(normalized * self.range))
        
        return dial_value
    
    def _default_formatter(self, value: float) -> str:
        """
        Default formatter for parameter values.
        
        Args:
            value: Parameter value
            
        Returns:
            Formatted string representation
        """
        # Use fewer decimal places for larger values
        if abs(value) >= 100:
            return f"{value:.1f}"
        elif abs(value) >= 10:
            return f"{value:.2f}"
        else:
            return f"{value:.3f}"
    
    def set_value(self, value: float) -> None:
        """
        Set the parameter value.
        
        Args:
            value: Parameter value to set
        """
        # Convert parameter value to dial value
        dial_value = self._param_to_dial(value)
        
        # Update the dial (this will trigger the valueChanged signal)
        self.dial.setValue(dial_value)
    
    def get_value(self) -> float:
        """
        Get the current parameter value.
        
        Returns:
            Current parameter value
        """
        return self._dial_to_param(self.dial.value())
#!/usr/bin/env python3
"""
Simple Mono Synth UI

A basic UI for the Simple Mono synth preset.
"""
import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget,
    QSlider, QDial, QHBoxLayout, QGroupBox, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal as Signal, QObject
from PyQt6.QtGui import QFont

from lib.common.utils import set_app_icon, LOG
from pythonosc import udp_client

# Default OSC settings for communicating with the router
OSC_IP = "127.0.0.1"
OSC_PORT = 9000
ROUTER_NAME = "router"

class ParameterDial(QWidget):
    """A dial with a label for controlling synth parameters."""
    
    value_changed = Signal(str, float)
    
    def __init__(self, name, label, min_val=0, max_val=127, default=64, parent=None):
        """Initialize the parameter dial."""
        super().__init__(parent)
        self.name = name
        
        layout = QVBoxLayout(self)
        
        # Create label
        self.label = QLabel(label)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)
        
        # Create dial
        self.dial = QDial()
        self.dial.setMinimum(min_val)
        self.dial.setMaximum(max_val)
        self.dial.setValue(default)
        self.dial.valueChanged.connect(self._value_changed)
        layout.addWidget(self.dial)
        
        # Create value label
        self.value_label = QLabel(str(default))
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.value_label)
        
    def _value_changed(self, value):
        """Handle dial value changed."""
        self.value_label.setText(str(value))
        # Normalize value to 0-1 range for OSC
        normalized = value / (self.dial.maximum() - self.dial.minimum())
        self.value_changed.emit(self.name, normalized)
        
    def set_value(self, value):
        """Set the dial value."""
        # Scale value from 0-1 to dial range
        scaled = int(value * (self.dial.maximum() - self.dial.minimum()))
        self.dial.setValue(scaled)

class SimpleSynthUI(QWidget):
    """Main widget for the Simple Mono synth UI."""
    
    def __init__(self, parent=None):
        """Initialize the UI."""
        super().__init__(parent)
        
        # Create OSC client for communicating with the router
        self.osc_client = udp_client.SimpleUDPClient(OSC_IP, OSC_PORT)
        
        # Create main layout
        main_layout = QVBoxLayout(self)
        
        # Add title
        title_label = QLabel("Simple Mono Synth")
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)
        
        # Create oscillator section
        osc_group = QGroupBox("Oscillator")
        osc_layout = QHBoxLayout()
        
        # Create oscillator parameters
        self.waveform_dial = ParameterDial("waveform", "Waveform", 0, 3, 0)
        self.detune_dial = ParameterDial("detune", "Detune", 0, 100, 0)
        self.octave_dial = ParameterDial("octave", "Octave", -2, 2, 0)
        
        # Connect parameter signals
        self.waveform_dial.value_changed.connect(self.parameter_changed)
        self.detune_dial.value_changed.connect(self.parameter_changed)
        self.octave_dial.value_changed.connect(self.parameter_changed)
        
        # Add parameters to layout
        osc_layout.addWidget(self.waveform_dial)
        osc_layout.addWidget(self.detune_dial)
        osc_layout.addWidget(self.octave_dial)
        osc_group.setLayout(osc_layout)
        main_layout.addWidget(osc_group)
        
        # Create filter section
        filter_group = QGroupBox("Filter")
        filter_layout = QHBoxLayout()
        
        # Create filter parameters
        self.cutoff_dial = ParameterDial("cutoff", "Cutoff", 0, 127, 100)
        self.resonance_dial = ParameterDial("resonance", "Resonance", 0, 127, 0)
        self.env_amount_dial = ParameterDial("env_amount", "Env Amount", 0, 127, 100)
        
        # Connect parameter signals
        self.cutoff_dial.value_changed.connect(self.parameter_changed)
        self.resonance_dial.value_changed.connect(self.parameter_changed)
        self.env_amount_dial.value_changed.connect(self.parameter_changed)
        
        # Add parameters to layout
        filter_layout.addWidget(self.cutoff_dial)
        filter_layout.addWidget(self.resonance_dial)
        filter_layout.addWidget(self.env_amount_dial)
        filter_group.setLayout(filter_layout)
        main_layout.addWidget(filter_group)
        
        # Create envelope section
        env_group = QGroupBox("Envelope")
        env_layout = QHBoxLayout()
        
        # Create envelope parameters
        self.attack_dial = ParameterDial("attack", "Attack", 0, 127, 10)
        self.decay_dial = ParameterDial("decay", "Decay", 0, 127, 30)
        self.sustain_dial = ParameterDial("sustain", "Sustain", 0, 127, 100)
        self.release_dial = ParameterDial("release", "Release", 0, 127, 50)
        
        # Connect parameter signals
        self.attack_dial.value_changed.connect(self.parameter_changed)
        self.decay_dial.value_changed.connect(self.parameter_changed)
        self.sustain_dial.value_changed.connect(self.parameter_changed)
        self.release_dial.value_changed.connect(self.parameter_changed)
        
        # Add parameters to layout
        env_layout.addWidget(self.attack_dial)
        env_layout.addWidget(self.decay_dial)
        env_layout.addWidget(self.sustain_dial)
        env_layout.addWidget(self.release_dial)
        env_group.setLayout(env_layout)
        main_layout.addWidget(env_group)
        
        # Create panic button section
        panic_layout = QHBoxLayout()
        self.panic_button = QPushButton("PANIC")
        self.panic_button.setStyleSheet("background-color: #550000; color: white; font-weight: bold; padding: 10px;")
        self.panic_button.clicked.connect(self.send_panic)
        panic_layout.addWidget(self.panic_button)
        main_layout.addLayout(panic_layout)
    
    def parameter_changed(self, name, value):
        """Handle parameter value changed."""
        LOG.info(f"Parameter changed: {name} = {value}")
        try:
            # Send parameter to router
            self.osc_client.send_message(f"/{ROUTER_NAME}/param", [name, value])
        except Exception as e:
            LOG.error(f"Error sending parameter: {e}")
    
    def send_panic(self):
        """Send panic (all notes off) message to router."""
        LOG.info("Sending panic message")
        try:
            self.osc_client.send_message(f"/{ROUTER_NAME}/all_notes_off", [])
        except Exception as e:
            LOG.error(f"Error sending panic message: {e}")

def create_ui_widget(parent=None):
    """
    Create the UI widget for embedding in the main launcher.
    
    Args:
        parent: Optional parent widget
        
    Returns:
        The synth UI widget
    """
    try:
        LOG.info("Creating Simple Mono Synth UI widget")
        return SimpleSynthUI(parent)
    except Exception as e:
        LOG.error(f"Error creating synth UI widget: {e}")
        import traceback
        traceback.print_exc()
        # Create a fallback widget with error message
        fallback = QWidget(parent)
        layout = QVBoxLayout(fallback)
        error_label = QLabel(f"Error loading synth UI: {str(e)}")
        error_label.setStyleSheet("color: red;")
        layout.addWidget(error_label)
        return fallback

class StandaloneSynthUI(QMainWindow):
    """Standalone window for running the synth UI independently."""
    
    def __init__(self):
        """Initialize the standalone UI."""
        super().__init__()
        
        # Set window properties
        self.setWindowTitle("Simple Mono Synth")
        self.resize(2224, 1668)  # iPad dimensions
        
        # Create central widget
        central_widget = create_ui_widget()
        self.setCentralWidget(central_widget)
        
        # Add status bar
        self.statusBar().showMessage("Synth UI ready")

def main():
    """Main entry point for the synth UI when run standalone."""
    app = QApplication(sys.argv)
    
    # Set custom app icon if available - use try/except to handle failures
    try:
        set_app_icon(app)
    except Exception as e:
        LOG.warning(f"Could not set app icon: {e}")
    
    # Create and show the standalone UI
    window = StandaloneSynthUI()
    window.show()
    
    # Enter the application main loop
    return app.exec() if hasattr(app, 'exec') else app.exec_()

if __name__ == "__main__":
    sys.exit(main())


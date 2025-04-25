"""
MIDI tab for Caelus.

This module provides a tab for MIDI port selection and MIDI activity monitoring.
"""
from typing import Optional, List, Dict, Any, Callable
import time

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QComboBox, QFrame, QGridLayout
)
from PyQt6.QtCore import QTimer, pyqtSignal as Signal

from lib.common.utils import LOG
from core.controllers.midi_controller_wrapper import MidiControllerWrapper
from ui.tabs.base_tab import BaseTab
from ui.widgets.activity_light import ActivityLight
from ui.widgets.status_display import StatusDisplay

class MidiTab(BaseTab):
    """
    Tab for MIDI port selection and monitoring.
    
    Features:
    - MIDI port selection dropdown
    - Port refresh button
    - MIDI activity indicator
    - Auto-refresh port list
    """
    
    # Signal emitted when a MIDI port is connected
    midi_port_connected = Signal(str)  # (port_name)
    
    # Signal emitted when MIDI activity occurs
    midi_activity = Signal(bool)  # (active)
    
    def __init__(
        self,
        midi_controller: MidiControllerWrapper,
        auto_select_first_port: bool = False,
        refresh_interval: int = 3000,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize the MIDI tab.
        
        Args:
            midi_controller: MIDI controller wrapper
            auto_select_first_port: Whether to automatically select the first port
            refresh_interval: Interval in ms for port list refresh
            parent: Parent widget
        """
        # Store parameters first so they're available to _setup_ui()
        self.midi_controller = midi_controller
        self.auto_select_first_port = auto_select_first_port
        self.refresh_interval = refresh_interval
        
        # Call parent init (which calls _setup_ui)
        super().__init__(parent)
        
        # Set tab name
        self.tab_name = "MIDI"
        
        # Refresh port list initially
        self._refresh_midi_ports()
        
        # Timer for auto-refresh
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._update_midi_ports)
        self.refresh_timer.start(self.refresh_interval)
    
    def _setup_ui(self) -> None:
        """Set up the user interface."""
        # Create layout first
        super()._setup_ui()
        
        # Check if the layout was created
        if not hasattr(self, 'layout_obj'):
            raise RuntimeError("BaseTab._setup_ui() did not create layout_obj")
            
        # Header section
        header_label = QLabel("MIDI Configuration")
        header_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFA500;")
        self.layout_obj.addWidget(header_label)
        
        # Port selection section
        port_layout = QVBoxLayout()
        port_layout.addWidget(QLabel("MIDI Input Port:"))
        
        # MIDI port dropdown
        self.midi_dropdown = QComboBox()
        self.midi_dropdown.setStyleSheet("""
            QComboBox { 
                background-color: #222; 
                color: #CCCCCC;
                border: 1px solid #FFA500; 
                padding: 6px; 
            }
        """)
        self.midi_dropdown.currentIndexChanged.connect(self._on_port_changed)
        port_layout.addWidget(self.midi_dropdown)
        
        # Refresh button
        refresh_button = QPushButton("Refresh MIDI Ports")
        refresh_button.setStyleSheet("""
            QPushButton { 
                background-color: #222; 
                color: #CCCCCC;
                border: 1px solid #FFA500; 
                padding: 6px; 
            }
            QPushButton:hover { 
                background-color: #333; 
            }
        """)
        refresh_button.clicked.connect(self._refresh_midi_ports)
        port_layout.addWidget(refresh_button)
        
        self.layout_obj.addLayout(port_layout)
        
        # Activity indicators section
        indicator_layout = QHBoxLayout()
        
        # MIDI activity light
        self.midi_light = ActivityLight(
            label="MIDI IN",
            active_color="#FFA500",  # Orange
            inactive_color="#333333"
        )
        indicator_layout.addWidget(self.midi_light)
        
        # OSC activity light
        self.osc_light = ActivityLight(
            label="OSC OUT",
            active_color="#FFA500",  # Orange
            inactive_color="#333333"
        )
        indicator_layout.addWidget(self.osc_light)
        
        self.layout_obj.addLayout(indicator_layout)
        
        # Status display
        self.status_display = StatusDisplay(
            initial_text="Ready",
            initial_color="#00FF00",  # Green
            font_size=14
        )
        self.layout_obj.addWidget(self.status_display)
        
        # Add spacer at the bottom
        self.layout_obj.addStretch()
    
    def _refresh_midi_ports(self) -> None:
        """Refresh the list of available MIDI ports."""
        # Clear dropdown
        self.midi_dropdown.clear()
        
        # Get available ports
        ports = self.midi_controller.list_ports()
        LOG.info(f"Available MIDI ports: {ports}")
        
        if not ports:
            # No ports available
            self.midi_dropdown.addItem("-- No MIDI ports found --")
            self.status_display.update_status("error", "No MIDI ports found")
        else:
            # Add ports to dropdown
            self.midi_dropdown.addItems(ports)
            
            # Auto-select first port if enabled
            if self.auto_select_first_port or len(ports) == 1:
                LOG.info(f"Auto-selecting MIDI port: {ports[0]}")
                self.midi_dropdown.setCurrentIndex(0)
                self._on_port_changed(0)
    
    def _update_midi_ports(self) -> None:
        """Periodically update MIDI ports if they've changed."""
        # Get current ports in dropdown
        current_ports = [self.midi_dropdown.itemText(i) for i in range(self.midi_dropdown.count())]
        
        # Get available ports
        try:
            import mido
            available_ports = mido.get_input_names()
        except (ImportError, SystemError) as e:
            LOG.error(f"Error getting MIDI ports: {e}")
            return
        
        # Check if ports have changed
        if sorted(current_ports) != sorted(available_ports):
            # Remember current selection
            selected = self.midi_dropdown.currentText()
            
            # Block signals during update
            self.midi_dropdown.blockSignals(True)
            
            # Update dropdown
            self.midi_dropdown.clear()
            self.midi_dropdown.addItems(available_ports)
            
            # Restore selection if possible
            if selected in available_ports:
                self.midi_dropdown.setCurrentText(selected)
                
            # Unblock signals
            self.midi_dropdown.blockSignals(False)
            
            # Log port change
            LOG.info(f"MIDI ports changed: {available_ports}")
    
    def _on_port_changed(self, index: int) -> None:
        """
        Handle MIDI port selection.
        
        Args:
            index: Index of selected port in dropdown
        """
        if index < 0:
            # No selection
            self.status_display.update_status("warning", "No MIDI port selected")
            return
            
        # Get port name
        port_name = self.midi_dropdown.currentText()
        
        if "No MIDI ports found" in port_name:
            # Invalid port
            self.status_display.update_status("warning", "No valid MIDI port available")
            return
            
        # Try to connect to port
        LOG.info(f"Connecting to MIDI port: {port_name}")
        
        if self.midi_controller.select_port(port_name):
            # Connection successful
            self.status_display.update_status("info", f"Connected to MIDI port: {port_name}")
            self.midi_port_connected.emit(port_name)
        else:
            # Connection failed
            self.status_display.update_status("error", f"Failed to connect to MIDI port: {port_name}")
    
    def update_midi_light(self, active: bool) -> None:
        """
        Update MIDI activity light.
        
        Args:
            active: Whether the light should be active
        """
        self.midi_light.set_active(active)
        
        # Forward signal
        self.midi_activity.emit(active)
    
    def update_osc_light(self, active: bool) -> None:
        """
        Update OSC activity light.
        
        Args:
            active: Whether the light should be active
        """
        self.osc_light.set_active(active)
    
    def on_tab_activated(self) -> None:
        """Handle tab activation event."""
        super().on_tab_activated()
        
        # Refresh port list on activation
        self._refresh_midi_ports()
    
    def reset(self) -> None:
        """Reset tab to default state."""
        # Clear lights
        self.midi_light.set_active(False)
        self.osc_light.set_active(False)
        
        # Reset status
        self.status_display.update_status("info", "Ready")
        
        # Refresh port list
        self._refresh_midi_ports()
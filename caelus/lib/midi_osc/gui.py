"""
MIDI-OSC Bridge GUI Component

This module contains the GUI components for the MIDI-OSC bridge.
Focuses exclusively on MIDI-to-OSC conversion.
"""
import os
import time
import threading
from typing import Optional, Any, Dict, List, Callable

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QComboBox, QFrame, QMessageBox
)
from PyQt6.QtCore import QTimer, pyqtSignal as Signal, QObject
from pythonosc import udp_client

from lib.core.utils import LOG
from lib.midi_osc.midi_worker import MidiWorker
from lib.midi_osc.helpers import send_osc

# Signal handlers for UI updates and OSC communication
class UISignalHandler(QObject):
    """Handler for thread-safe UI updates."""
    midi_light_update = Signal(bool)
    osc_light_update = Signal(bool)
    status_update = Signal(str, str)  # color, text

class MidiOscGui(QWidget):
    """
    MIDI-OSC Bridge GUI
    
    Focused component for converting MIDI messages to OSC.
    Handles MIDI port selection, message conversion, and visualization.
    Does NOT include synth bank loading or voice management.
    """
    def __init__(
        self, 
        osc_ip: str = "127.0.0.1", 
        osc_port: int = 9001, 
        router_name: str = "router", 
        presets_dir: str = "presets", 
        ui_osc_port: int = 9002,
        auto_select_first_interface: bool = False,
        parent: Optional[QWidget] = None
    ) -> None:
        """
        Initialize the MIDI-OSC bridge GUI.
        
        Args:
            osc_ip: IP address of the OSC router
            osc_port: Port of the OSC router
            router_name: Name of the OSC router
            presets_dir: Directory containing synth presets (unused in this class)
            ui_osc_port: Port to listen on for UI feedback (unused in this class)
            auto_select_first_interface: Whether to automatically select the first MIDI interface
            parent: Parent widget (if None, this widget is a top-level window)
        """
        super().__init__(parent)
        self.osc_ip: str = osc_ip
        self.osc_port: int = osc_port
        self.router_name: str = router_name
        self.auto_select_first_interface: bool = auto_select_first_interface
        
        # MIDI worker setup
        self.midi_worker: Optional[MidiWorker] = None
        self.midi_in_port: Optional[str] = None
        
        # Set up UI signal handler for thread-safe updates
        self.ui_signal_handler = UISignalHandler()
        self.ui_signal_handler.midi_light_update.connect(self.update_midi_light)
        self.ui_signal_handler.osc_light_update.connect(self.update_osc_light)
        self.ui_signal_handler.status_update.connect(self.update_status)
        
        # Create OSC client
        self.osc_client: udp_client.SimpleUDPClient = udp_client.SimpleUDPClient(self.osc_ip, self.osc_port)
        
        self.setWindowTitle("Caelus MIDI↔OSC Bridge")
        self.setStyleSheet("""
            QWidget { background-color: #111; color: #FFA500; font-family: 'SF Mono', 'Menlo', 'Monaco', monospace; }
            QComboBox, QPushButton { background-color: #222; border: 1px solid #FFA500; padding: 6px; }
            QLabel { font-size: 16px; }
        """)

        self.setup_ui()
        
    def setup_ui(self) -> None:
        """Set up the user interface components."""
        layout = QVBoxLayout()

        # --- MIDI Dropdown ---
        midi_layout = QVBoxLayout()
        midi_layout.addWidget(QLabel("MIDI Input Port:"))
        
        self.midi_dropdown = QComboBox()
        self.refresh_midi_ports()
        self.midi_dropdown.currentIndexChanged.connect(self.midi_port_changed)
        midi_layout.addWidget(self.midi_dropdown)
        
        # Add refresh button for MIDI ports
        midi_refresh_btn = QPushButton("Refresh MIDI Ports")
        midi_refresh_btn.clicked.connect(self.refresh_midi_ports)
        midi_layout.addWidget(midi_refresh_btn)
        
        layout.addLayout(midi_layout)

        # OSC connection info
        layout.addWidget(QLabel(f"OSC Router: {self.osc_ip}:{self.osc_port}"))

        # --- Status info ---
        self.status_label = QLabel("Ready - Connect MIDI interface")
        self.status_label.setStyleSheet("color: #AAAAAA; font-size: 14px;")
        layout.addWidget(self.status_label)

        # --- Lights ---
        light_row = QHBoxLayout()
        self.midi_light = QLabel()
        self.osc_light = QLabel()
        for light in (self.midi_light, self.osc_light):
            light.setFixedSize(30, 30)
            light.setFrameShape(QFrame.Shape.NoFrame)
            light.setStyleSheet("""
                background-color: #333;
                border-radius: 15px;
                border: 2px solid #FFA500;
            """)
            # Initialize lights as off (already done by styleSheet above)

        light_row.addWidget(QLabel("MIDI IN"))
        light_row.addWidget(self.midi_light)
        light_row.addSpacing(20)
        light_row.addWidget(QLabel("OSC OUT"))
        light_row.addWidget(self.osc_light)
        layout.addLayout(light_row)

        # --- Buttons ---
        button_row = QHBoxLayout()
        
        # Add panic button to clear stuck notes
        self.panic_btn = QPushButton("PANIC")
        self.panic_btn.setStyleSheet("background-color: #550000; font-weight: bold;")
        self.panic_btn.clicked.connect(self.panic)
        button_row.addWidget(self.panic_btn)
        
        # Add a close button
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.close)
        button_row.addWidget(self.close_btn)
        
        layout.addLayout(button_row)
        self.setLayout(layout)

        # Timer to auto turn off lights
        self.flash_timer = QTimer()
        self.flash_timer.timeout.connect(self.dim_lights)
        self.flash_timer.start(100)
        self.midi_recent = False
        self.osc_recent = False

        # Timer to rescan MIDI ports
        self.port_refresh_timer = QTimer()
        self.port_refresh_timer.timeout.connect(self.update_midi_ports)
        self.port_refresh_timer.start(3000)
    
    def refresh_midi_ports(self) -> None:
        """Refresh the list of available MIDI input ports."""
        self.midi_dropdown.clear()
        try:
            import mido
            ports = mido.get_input_names()
            LOG.info(f"Available MIDI ports: {ports}")
            
            if not ports:
                LOG.warning("WARNING: No MIDI ports found!")
                self.midi_dropdown.addItem("-- No MIDI ports found --")
                QMessageBox.warning(self, "MIDI Error", "No MIDI ports found! Please connect a MIDI device and click 'Refresh MIDI Ports'.")
            else:
                self.midi_dropdown.addItems(ports)
                # If auto-select is enabled or there's only one port, select it
                if self.auto_select_first_interface or len(ports) == 1:
                    LOG.info(f"Auto-selecting MIDI port: {ports[0]}")
                    self.midi_dropdown.setCurrentIndex(0)
                    self.midi_port_changed(0)  # Trigger the port selection logic
        except Exception as e:
            LOG.error(f"Error refreshing MIDI ports: {e}")
            self.midi_dropdown.addItem("-- Error getting MIDI ports --")

    def update_midi_ports(self) -> None:
        """Periodically update the list of MIDI ports if they've changed."""
        try:
            import mido
            current_ports = [self.midi_dropdown.itemText(i) for i in range(self.midi_dropdown.count())]
            available_ports = mido.get_input_names()
            if set(current_ports) != set(available_ports) and available_ports:  # Only update if ports changed and not empty
                selected = self.midi_dropdown.currentText()
                self.midi_dropdown.blockSignals(True)
                self.midi_dropdown.clear()
                self.midi_dropdown.addItems(available_ports)
                if selected in available_ports:
                    self.midi_dropdown.setCurrentText(selected)
                self.midi_dropdown.blockSignals(False)
        except Exception as e:
            # Don't log this error every time, as it could flood the logs
            pass

    def midi_port_changed(self, index: int) -> None:
        """
        Handle when the user selects a different MIDI port.
        
        Args:
            index: Index of the selected MIDI port in the dropdown
        """
        if self.midi_worker:
            self.midi_worker.stop()
            self.midi_worker = None
            LOG.info("Stopped existing MIDI worker")
        
        if index < 0:
            LOG.warning("No MIDI port selected")
            return
            
        port_name = self.midi_dropdown.currentText()
        LOG.info(f"Selected MIDI port: '{port_name}'")
        
        if "No MIDI ports found" in port_name or "Error" in port_name:
            LOG.warning("Cannot connect to invalid MIDI port")
            return
            
        try:
            import mido
            # Test if we can open the port
            LOG.info(f"Testing MIDI port: {port_name}")
            test_port = mido.open_input(port_name)
            test_port.close()
            LOG.info("MIDI port test successful")
            
            # Create the worker
            self.midi_worker = MidiWorker(port_name, self.handle_midi)
            self.midi_worker.start()
            LOG.info(f"Started MIDI worker for port: {port_name}")
            
            # Update UI
            self.update_status("#00FF00", f"Connected to MIDI port: {port_name}")
        except Exception as e:
            LOG.error(f"ERROR connecting to MIDI port: {e}")
            QMessageBox.warning(self, "MIDI Error", f"Failed to connect to MIDI port: {str(e)}")
            self.midi_worker = None
            self.update_status("#FF0000", f"Failed to connect to MIDI port: {str(e)}")
    
    def handle_midi(self, msg) -> None:
        """
        Handle incoming MIDI messages.
        
        Args:
            msg: MIDI message to process
        """
        try:
            # Signal UI thread to update MIDI light instead of direct update
            self.ui_signal_handler.midi_light_update.emit(True)
            
            # Skip messages we don't care about
            if msg.type not in ['note_on', 'note_off', 'control_change', 'pitchwheel', 'aftertouch', 'polytouch']:
                return
                
            LOG.debug(f"MIDI: {msg}")
            
            # Convert MIDI message to OSC
            if msg.type == 'note_on':
                if msg.velocity == 0:
                    # Note-on with velocity 0 is same as note-off
                    send_osc(self.osc_client, f"/{self.router_name}/note_off", [msg.note])
                    self.update_status("#00AAFF", f"Note Off: {msg.note}")
                else:
                    # Normalize velocity to 0-1 range
                    velocity = msg.velocity / 127.0
                    send_osc(self.osc_client, f"/{self.router_name}/note_on", [msg.note, velocity])
                    self.update_status("#00FFAA", f"Note On: {msg.note} vel: {velocity:.2f}")
                    
            elif msg.type == 'note_off':
                send_osc(self.osc_client, f"/{self.router_name}/note_off", [msg.note])
                self.update_status("#00AAFF", f"Note Off: {msg.note}")
                
            elif msg.type == 'control_change':
                # Normalize value to 0-1 range
                value = msg.value / 127.0
                
                # If CC 64 (sustain), handle specially
                if msg.control == 64:
                    sustain_state = "On" if value >= 0.5 else "Off"
                    send_osc(self.osc_client, f"/{self.router_name}/sustain", [value])
                    self.update_status("#FFAA00", f"Sustain: {sustain_state}")
                else:
                    send_osc(self.osc_client, f"/{self.router_name}/cc", [msg.control, value])
                    self.update_status("#AAFFAA", f"CC {msg.control}: {value:.2f}")
                
            elif msg.type == 'pitchwheel':
                # Normalize to -1 to 1 range
                pitch_bend = msg.pitch / 8192.0
                send_osc(self.osc_client, f"/{self.router_name}/pitch_bend", [pitch_bend])
                self.update_status("#FFAAFF", f"Pitch Bend: {pitch_bend:.2f}")
                
            elif msg.type == 'aftertouch':
                # Normalize to 0-1 range
                pressure = msg.value / 127.0
                send_osc(self.osc_client, f"/{self.router_name}/aftertouch", [pressure])
                self.update_status("#AAAAFF", f"Aftertouch: {pressure:.2f}")
                
            elif msg.type == 'polytouch':
                # Normalize to 0-1 range
                pressure = msg.value / 127.0
                send_osc(self.osc_client, f"/{self.router_name}/poly_aftertouch", [msg.note, pressure])
                self.update_status("#AAAAFF", f"Poly AT {msg.note}: {pressure:.2f}")
            
            # Signal UI thread to update OSC light
            self.ui_signal_handler.osc_light_update.emit(True)
                
        except Exception as e:
            LOG.error(f"Error handling MIDI message: {e}")
            import traceback
            traceback.print_exc()
            self.update_status("#FF0000", f"Error: {str(e)}")
    
    def update_status(self, color: str, message: str) -> None:
        """
        Update the status display with information.
        
        Args:
            color: CSS color string
            message: Status message to display
        """
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {color}; font-size: 14px;")
    
    def dim_lights(self) -> None:
        """Turn off activity lights after a short delay."""
        if not self.midi_recent:
            self.update_midi_light(False)
        if not self.osc_recent:
            self.update_osc_light(False)
        self.midi_recent = False
        self.osc_recent = False
    
    def closeEvent(self, event) -> None:
        """
        Handle window close event.
        
        Args:
            event: Close event
        """
        LOG.info("Closing MIDI-OSC bridge")
        
        # Stop MIDI worker
        if self.midi_worker:
            LOG.info("Stopping MIDI worker")
            self.midi_worker.stop()
        
        # Accept the close event
        event.accept()
    
    def panic(self) -> None:
        """
        Send emergency all notes off message to the router.
        
        This is the "panic button" to clear any stuck notes.
        """
        LOG.info("PANIC - sending all notes off")
        try:
            send_osc(self.osc_client, f"/{self.router_name}/all_notes_off", [])
            self.update_status("#FF0000", "All notes off - PANIC button pressed")
        except Exception as e:
            LOG.error(f"Error sending panic message: {e}")
            self.update_status("#FF0000", f"Error: {str(e)}")

    def update_midi_light(self, on: bool) -> None:
        """
        Update the MIDI activity light in a thread-safe way.
        
        Args:
            on: Whether the light should be on or off
        """
        color = "#FFA500" if on else "#333"
        self.midi_light.setStyleSheet(f"""
            background-color: {color};
            border-radius: 15px;
            border: 2px solid #FFA500;
        """)
        self.midi_recent = on
        
    def update_osc_light(self, on: bool) -> None:
        """
        Update the OSC activity light in a thread-safe way.
        
        Args:
            on: Whether the light should be on or off
        """
        color = "#FFA500" if on else "#333"
        self.osc_light.setStyleSheet(f"""
            background-color: {color};
            border-radius: 15px;
            border: 2px solid #FFA500;
        """)
        self.osc_recent = on
        
    def get_midi_port(self) -> Optional[str]:
        """Get the currently selected MIDI port name."""
        if self.midi_worker:
            return self.midi_in_port
        return None 
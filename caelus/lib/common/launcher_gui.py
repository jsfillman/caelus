"""
Caelus Launcher GUI Components

This module contains the GUI components for the Caelus launcher.
"""
import os
import time
import yaml
import threading
from typing import Dict, List, Optional, Any, Union, Callable, Tuple
import subprocess
import sys

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QComboBox, QFrame, QFileDialog, QMessageBox
)
from PyQt6.QtCore import QTimer, pyqtSignal as Signal, QObject
from pythonosc import udp_client

from lib.common.utils import LOG
from lib.midi_osc.midi_controller import MidiController
from lib.osc_bridge.ui_bridge_controller import UiBridgeController
from lib.common.bank_controller import BankController
from lib.common.patch_controller import PatchController
from lib.common.connectivity_controller import ConnectivityController
from lib.midi_osc.helpers import send_osc
from lib.midi_osc.midi_worker import MidiWorker

# Signal handlers for UI updates and OSC communication
class OSCSignalHandler(QObject):
    """Handler for OSC signals that communicates with the GUI."""
    status_updated = Signal(str, str)
    param_changed = Signal(str, float)

class UISignalHandler(QObject):
    """Handler for thread-safe UI updates."""
    midi_light_update = Signal(bool)
    osc_light_update = Signal(bool)
    status_update = Signal(str, str)  # color, text

class OSCServerThread(threading.Thread):
    """
    Thread to run OSC server in background.
    
    Listens for messages from the router and forwards them to the GUI.
    """
    def __init__(self, signal_handler: OSCSignalHandler, listen_port: int = 9002) -> None:
        """
        Initialize the OSC server thread.
        
        Args:
            signal_handler: Handler to emit signals to the GUI
            listen_port: Port to listen on for OSC messages
        """
        super().__init__(daemon=True)
        self.signal_handler: OSCSignalHandler = signal_handler
        self.listen_port: int = listen_port
        
        # We'll import these here to avoid circular imports
        from pythonosc.dispatcher import Dispatcher
        from pythonosc.osc_server import ThreadingOSCUDPServer
        
        self.dispatcher: Dispatcher = Dispatcher()
        self.running: bool = True
        self.server: Optional[ThreadingOSCUDPServer] = None
        
        # Set up handlers
        self.setup_handlers()
        
    def setup_handlers(self) -> None:
        """Set up OSC message handlers for different address patterns."""
        # Status message handler
        self.dispatcher.map("/ui/status", self.handle_status)
        
        # Parameter update handler
        self.dispatcher.map("/ui/param", self.handle_param_update)
        
        # Wildcard handler for debugging
        self.dispatcher.map("/*", self.handle_wildcard)
        
    def handle_status(self, address: str, *args: Any) -> None:
        """
        Handle status messages from router.
        
        Args:
            address: OSC address pattern
            *args: OSC arguments (status_type, message)
        """
        LOG.info(f"Received status OSC message: {address} {args}")
        if len(args) >= 2:
            status_type = str(args[0])
            message = str(args[1])
            LOG.info(f"Received status: {status_type} - {message}")
            # Emit signal for GUI to update
            self.signal_handler.status_updated.emit(status_type, message)
            
    def handle_param_update(self, address: str, *args: Any) -> None:
        """
        Handle parameter updates from router.
        
        Args:
            address: OSC address pattern
            *args: OSC arguments (param_name, value)
        """
        LOG.info(f"Received param OSC message: {address} {args}")
        if len(args) >= 2:
            param_name = str(args[0])
            value = float(args[1])
            LOG.info(f"Parameter update: {param_name} = {value}")
            # Emit signal for GUI to update
            self.signal_handler.param_changed.emit(param_name, value)
    
    def handle_wildcard(self, address: str, *args: Any) -> None:
        """
        Debug handler for all OSC messages.
        
        Args:
            address: OSC address pattern
            *args: OSC arguments
        """
        # Only log messages that aren't handled by dedicated handlers
        if not (address.startswith('/ui/status') or address.startswith('/ui/param')):
            LOG.info(f"Received wildcard OSC message: {address} {args}")
            LOG.debug(f"Received unhandled OSC: {address} {args}")
        
        # Don't attempt to reply or forward messages - that's likely causing the encoding errors
    
    def run(self) -> None:
        """Run the OSC server in a separate thread."""
        try:
            from pythonosc.osc_server import ThreadingOSCUDPServer
            
            self.server = ThreadingOSCUDPServer(("127.0.0.1", self.listen_port), self.dispatcher)
            LOG.info(f"OSC server listening on 127.0.0.1:{self.listen_port}")
            
            # Modified serve_forever loop that can be stopped
            count: int = 0
            last_log: float = time.time()
            try:
                while self.running:
                    # Handle any incoming message
                    try:
                        self.server.handle_request()
                    except Exception as e:
                        LOG.error(f"Error handling OSC request: {e}")
                    
                    # Log a heartbeat message occasionally to show we're still listening
                    count += 1
                    if count % 100 == 0 or time.time() - last_log > 10:
                        LOG.info(f"OSC server still listening on 127.0.0.1:{self.listen_port}...")
                        last_log = time.time()
            except KeyboardInterrupt:
                LOG.info("OSC server stopped by keyboard interrupt")
                self.running = False
                    
        except Exception as e:
            LOG.error(f"Error in OSC server: {e}")
            import traceback
            traceback.print_exc()
    
    def stop(self) -> None:
        """Stop the OSC server thread."""
        self.running = False
        if self.server:
            # Close the socket
            self.server.socket.close()
        LOG.info("OSC server stopped")

class LauncherGUI(QWidget):
    """
    Main GUI for the Caelus launcher.
    
    Provides the user interface for selecting MIDI devices,
    managing synth banks, and controlling the router.
    """
    def __init__(
        self, 
        osc_ip: str = "127.0.0.1", 
        osc_port: int = 9001, 
        router_name: str = "router", 
        presets_dir: str = "presets", 
        ui_osc_port: int = 9002,
        auto_select_first_interface: bool = False,
        default_bank: Optional[str] = None,
        on_bank_loaded: Optional[Callable[[str, str], None]] = None,
        parent: Optional[QWidget] = None
    ) -> None:
        """
        Initialize the Caelus launcher GUI.
        
        Args:
            osc_ip: IP address of the OSC router
            osc_port: Port of the OSC router
            router_name: Name of the OSC router
            presets_dir: Directory containing synth presets
            ui_osc_port: Port to listen on for UI feedback
            auto_select_first_interface: Whether to automatically select the first MIDI interface
            default_bank: Default bank to load on startup (if None, no bank is auto-loaded)
            on_bank_loaded: Callback function when a bank is loaded (receives bank_name, bank_dir)
            parent: Parent widget (if None, this widget is a top-level window)
        """
        # If parent is provided, set it as parent, otherwise create a top-level window
        super().__init__(parent)
        self.osc_ip: str = osc_ip
        self.osc_port: int = osc_port
        self.router_name: str = router_name
        self.presets_dir: str = presets_dir
        self.ui_osc_port: int = ui_osc_port
        self.auto_select_first_interface: bool = auto_select_first_interface
        self.default_bank: Optional[str] = default_bank
        self.on_bank_loaded: Optional[Callable[[str, str], None]] = on_bank_loaded
        
        # Initialize OSC client for communicating with the router
        from pythonosc import udp_client
        self.osc_client = udp_client.SimpleUDPClient(self.osc_ip, self.osc_port)
        
        # Initialize worker to None before setup_ui() is called
        self.worker = None
        self.synth_processes = []
        
        # Initialize signal handlers for thread-safe UI updates
        self.ui_signal_handler = UISignalHandler()
        self.ui_signal_handler.midi_light_update.connect(self.update_midi_light)
        self.ui_signal_handler.osc_light_update.connect(self.update_osc_light)
        
        # Instantiate controllers
        self.midi_ctrl = MidiController()
        self.midi_ctrl.midi_light_update.connect(self.update_midi_light)
        self.midi_ctrl.midi_event.connect(self.handle_midi)

        self.osc_ui = UiBridgeController(listen_port=self.ui_osc_port)
        self.osc_ui.status_updated.connect(self.update_status)
        self.osc_ui.param_changed.connect(self.update_parameter)
        self.osc_ui.start()

        self.bank_ctrl = BankController(
            presets_dir=self.presets_dir,
            osc_ip=self.osc_ip,
            osc_port=self.osc_port,
            router_name=self.router_name,
            ui_osc_port=self.ui_osc_port
        )

        self.patch_ctrl = PatchController(
            presets_dir=self.presets_dir,
            osc_client=self.osc_client,
            router_name=self.router_name
        )
        self.patch_ctrl.patch_loaded.connect(
            lambda name: self.update_status_direct("#00FF00", f"Loaded patch: {name}")
        )
        self.patch_ctrl.error.connect(
            lambda msg: QMessageBox.critical(self, "Patch Error", msg)
        )

        self.conn_ctrl = ConnectivityController()
        self.conn_ctrl.connectivity_changed.connect(
            lambda alive, total: self.update_status_direct(
                "#00FFAA", f"Synths connected: {alive}/{total}"
            )
        )

        self.setWindowTitle("Caelus MIDI↔OSC Bridge")
        self.setStyleSheet("""
            QWidget { background-color: #111; color: #FFA500; font-family: 'SF Mono', 'Menlo', 'Monaco', monospace; }
            QComboBox, QPushButton { background-color: #222; border: 1px solid #FFA500; padding: 6px; }
            QLabel { font-size: 16px; }
        """)

        self.setup_ui()
        
        # Auto-load default bank if specified
        if self.default_bank:
            QTimer.singleShot(500, lambda: self.load_default_bank())
    
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

        # --- Bank Selection ---
        self.bank_dropdown = QComboBox()
        self.refresh_bank_list()
        self.bank_dropdown.currentIndexChanged.connect(self.bank_changed)
        layout.addWidget(QLabel("Synth Bank:"))
        layout.addWidget(self.bank_dropdown)

        # --- Status info ---
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #00FF00; font-size: 14px;")
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
        
        self.load_bank_btn = QPushButton("Load Bank")
        self.load_bank_btn.clicked.connect(self.load_bank)
        
        self.load_patch_btn = QPushButton("Load Patch")
        self.load_patch_btn.clicked.connect(self.load_patch)
        
        self.save_patch_btn = QPushButton("Save Patch")
        self.save_patch_btn.clicked.connect(self.save_patch)
        
        # Add panic button to clear stuck notes
        self.panic_btn = QPushButton("PANIC")
        self.panic_btn.setStyleSheet("background-color: #550000; font-weight: bold;")
        self.panic_btn.clicked.connect(self.panic)
        
        # Initially disable buttons until a bank is selected
        self.update_button_state(False)
        
        for button in [self.load_bank_btn, self.load_patch_btn, self.save_patch_btn, self.panic_btn]:
            button_row.addWidget(button)
        layout.addLayout(button_row)

        self.setLayout(layout)
        self.current_bank = None
        self.current_patch = None

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

    # Import all the necessary methods from the old GUI class
    # Only showing method signatures here for brevity
    # Full implementation will be added in a subsequent step
    
    def update_status(self, status_type: str, message: str) -> None:
        """Update status display with info from router."""
        color = "#FFFFFF"  # Default white
        if status_type == "info":
            color = "#00FF00"  # Green
        elif status_type == "warning":
            color = "#FFAA00"  # Orange
        elif status_type == "error":
            color = "#FF0000"  # Red
        elif status_type == "note":
            color = "#00AAFF"  # Light blue
            
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {color}; font-size: 14px;")
    
    def update_parameter(self, param_name: str, value: float) -> None:
        """Update UI elements based on parameter changes from router."""
        LOG.info(f"UI received parameter update: {param_name} = {value}")
        
        # Handle special parameters
        if param_name == "cutoff":
            # Color the status to show parameter activity
            self.status_label.setText(f"Cutoff: {value:.1f} Hz")
            self.status_label.setStyleSheet("color: #00FFAA; font-size: 14px;")
            self.osc_recent = True
        elif param_name == "modulation":
            self.status_label.setText(f"Modulation: {value:.2f}")
            self.status_label.setStyleSheet("color: #00AAFF; font-size: 14px;")
            self.osc_recent = True
        elif param_name.startswith("cc"):
            # For generic CC messages
            cc_num = param_name[2:]
            self.status_label.setText(f"CC {cc_num}: {value:.2f}")
            self.status_label.setStyleSheet("color: #AAFFAA; font-size: 14px;")
            self.osc_recent = True 

    def refresh_midi_ports(self) -> None:
        """Refresh the list of available MIDI input ports."""
        self.midi_dropdown.clear()
        ports = self.midi_ctrl.list_ports()
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

    def refresh_bank_list(self) -> None:
        """Refresh the list of available synth banks from the presets directory."""
        self.bank_dropdown.clear()
        try:
            self.bank_dropdown.addItem("-- Select Synth --")
            banks = self.bank_ctrl.list_banks()
            self.bank_dropdown.addItems(banks)
        except Exception as e:
            LOG.error(f"Error loading banks: {e}")

    def update_midi_ports(self) -> None:
        """Periodically update the list of MIDI ports if they've changed."""
        import mido
        current_ports = [self.midi_dropdown.itemText(i) for i in range(self.midi_dropdown.count())]
        available_ports = mido.get_input_names()
        if current_ports != available_ports:
            selected = self.midi_dropdown.currentText()
            self.midi_dropdown.blockSignals(True)
            self.midi_dropdown.clear()
            self.midi_dropdown.addItems(available_ports)
            if selected in available_ports:
                self.midi_dropdown.setCurrentText(selected)
            self.midi_dropdown.blockSignals(False)

    def midi_port_changed(self, index: int) -> None:
        """
        Handle when the user selects a different MIDI port.
        
        Args:
            index: Index of the selected MIDI port in the dropdown
        """
        if self.worker:
            self.worker.stop()
            self.worker = None
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
            self.worker = MidiWorker(port_name, self.handle_midi)
            self.worker.start()
            LOG.info(f"Started MIDI worker for port: {port_name}")
        except Exception as e:
            LOG.error(f"ERROR connecting to MIDI port: {e}")
            QMessageBox.warning(self, "MIDI Error", f"Failed to connect to MIDI port: {str(e)}")
            self.worker = None

    def bank_changed(self, index: int) -> None:
        """
        Handle when the user selects a different synth bank.
        
        Args:
            index: Index of the selected bank in the dropdown
        """
        if index <= 0:  # Skip the "-- Select Synth --" entry
            self.update_button_state(False)
            return

        bank_name = self.bank_dropdown.currentText()
        LOG.info(f"Selected bank: {bank_name}")
        
        self.current_bank = bank_name
        self.update_button_state(True)
        
        # Ask user if they want to load the bank
        response = QMessageBox.question(
            self,
            "Load Bank",
            f"Do you want to load the bank '{bank_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if response == QMessageBox.StandardButton.Yes:
            LOG.info(f"Auto-loading bank: {bank_name}")
            self.load_bank()

    def load_bank(self) -> None:
        """Load the currently selected synth bank."""
        bank_name = self.bank_dropdown.currentText()
        if not bank_name or bank_name == "-- Select Synth --":
            LOG.warning("No valid bank selected - please select a bank first")
            QMessageBox.warning(self, "Bank Error", "Please select a synth bank first")
            return
        try:
            LOG.info(f"Loading synth bank: {bank_name}")
            counts = self.bank_ctrl.load_bank(bank_name)
            LOG.info(f"Bank '{bank_name}' loaded: {counts['local']} local, {counts['remote']} remote synths")
            self.status_label.setText(
                f"Bank '{bank_name}' loaded with {counts['local']} local and {counts['remote']} remote synths"
            )
            self.status_label.setStyleSheet("color: #00FF00; font-size: 14px;")
            self.update_button_state(True)
            if self.on_bank_loaded:
                bank_dir = os.path.join(self.presets_dir, bank_name)
                self.on_bank_loaded(bank_name, bank_dir)
        except Exception as e:
            LOG.error(f"Error loading bank: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load bank: {e}")
            self.update_button_state(False)

    def load_patch_file(self, patch_file: str) -> bool:
        """
        Load a patch file and apply it to the current synth.
        
        Args:
            patch_file: Path to the patch file to load
            
        Returns:
            True if patch was loaded successfully, False otherwise
        """
        try:
            if not os.path.exists(patch_file):
                raise FileNotFoundError(f"Patch file {patch_file} not found")
                
            LOG.info(f"Loading patch from: {patch_file}")
            with open(patch_file, 'r') as f:
                patch_data = yaml.safe_load(f)
            
            # Store current patch
            self.current_patch = patch_file
            
            # Apply patch to synth
            if not isinstance(patch_data, dict):
                raise ValueError(f"Invalid patch format in {patch_file}")
                
            LOG.info(f"Applying patch parameters: {patch_data}")
            
            # Send parameters to synth
            for param_name, value in patch_data.items():
                # Skip metadata sections
                if param_name.startswith('_'):
                    continue
                    
                LOG.info(f"Setting parameter: {param_name} = {value}")
                send_osc(self.osc_client, f"/{self.router_name}/param", [param_name, float(value)])
                time.sleep(0.01)  # Small delay to avoid flooding
            
            # Extract patch name for status display
            patch_name = os.path.basename(patch_file).replace('.yaml', '')
            metadata = patch_data.get('_metadata', {})
            if isinstance(metadata, dict) and 'name' in metadata:
                patch_name = metadata['name']
                
            LOG.info(f"Loaded patch: {patch_name}")
            self.status_label.setText(f"Loaded patch: {patch_name}")
            self.status_label.setStyleSheet("color: #00FF00; font-size: 14px;")
            
            # Delegate to PatchController
            self.patch_ctrl.load_patch(self.current_bank, patch_file)
            return True
            
        except Exception as e:
            LOG.error(f"Error loading patch: {e}")
            self.status_label.setText(f"Error loading patch: {str(e)}")
            self.status_label.setStyleSheet("color: #FF0000; font-size: 14px;")
            return False
    
    def load_patch(self) -> None:
        """Open file dialog to select and load a patch file."""
        if not self.current_bank:
            QMessageBox.warning(self, "Warning", "Please select a bank first")
            return
            
        patches_dir = os.path.join(self.presets_dir, self.current_bank, "patches")
        if not os.path.exists(patches_dir):
            os.makedirs(patches_dir)
            
        filename, _ = QFileDialog.getOpenFileName(
            self, "Load Patch", patches_dir, "YAML Files (*.yaml *.yml)"
        )
        
        if filename:
            self.load_patch_file(filename)
    
    def save_patch(self) -> None:
        """Save current synth state to a patch file."""
        if not self.current_bank:
            QMessageBox.warning(self, "Warning", "Please select a bank first")
            return
            
        patches_dir = os.path.join(self.presets_dir, self.current_bank, "patches")
        if not os.path.exists(patches_dir):
            os.makedirs(patches_dir)
            
        # Let user choose filename
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Patch", patches_dir, "YAML Files (*.yaml)"
        )
        
        if not filename:
            return
            
        if not filename.endswith('.yaml'):
            filename += '.yaml'
            
        # For now, create a simple patch template
        # In a real implementation, you'd query the synth for current parameter values
        patch_data = {
            "_metadata": {
                "name": os.path.basename(filename).replace('.yaml', ''),
                "author": "Caelus User",
                "description": "Saved patch",
                "created": time.strftime("%Y-%m-%d %H:%M:%S")
            },
            "cutoff": 1000.0,
            "resonance": 0.5,
            "attack": 0.01,
            "decay": 0.1,
            "sustain": 0.7,
            "release": 0.5,
            "gain": 0.8
        }
        
        if filename:
            patch_name = os.path.basename(filename).replace('.yaml', '')
            self.patch_ctrl.save_patch(self.current_bank, patch_name, patch_data)
    
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
                else:
                    # Normalize velocity to 0-1 range
                    velocity = msg.velocity / 127.0
                    send_osc(self.osc_client, f"/{self.router_name}/note_on", [msg.note, velocity])
                    
            elif msg.type == 'note_off':
                send_osc(self.osc_client, f"/{self.router_name}/note_off", [msg.note])
                
            elif msg.type == 'control_change':
                # If CC 64 (sustain), handle specially
                if msg.control == 64:
                    send_osc(self.osc_client, f"/{self.router_name}/sustain", [msg.value])
                else:
                    send_osc(self.osc_client, f"/{self.router_name}/cc", [msg.control, msg.value])
                
            elif msg.type == 'pitchwheel':
                # Normalize to -1 to 1 range
                pitch_bend = msg.pitch / 8192.0
                send_osc(self.osc_client, f"/{self.router_name}/pitch_bend", [pitch_bend])
                
            elif msg.type == 'aftertouch':
                # Normalize to 0-1 range
                pressure = msg.value / 127.0
                send_osc(self.osc_client, f"/{self.router_name}/aftertouch", [pressure])
                
            elif msg.type == 'polytouch':
                # Normalize to 0-1 range
                pressure = msg.value / 127.0
                send_osc(self.osc_client, f"/{self.router_name}/poly_aftertouch", [msg.note, pressure])
            
            # Signal UI thread to update OSC light
            self.ui_signal_handler.osc_light_update.emit(True)
                
        except Exception as e:
            LOG.error(f"Error handling MIDI message: {e}")
            import traceback
            traceback.print_exc()
    
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
        
        # Stop OSC UI bridge
        self.osc_ui.stop()
        
        # Stop MIDI controller
        self.midi_ctrl.stop()
        
        # Kill all child processes
        LOG.info("Stopping all child processes")
        # Use patch or bank controllers cleanup if needed
        from lib.midi_osc.helpers import kill_all_processes
        kill_all_processes()
        
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
            self.status_label.setText("All notes off - PANIC button pressed")
            self.status_label.setStyleSheet("color: #FF0000; font-size: 14px;")
        except Exception as e:
            LOG.error(f"Error sending panic message: {e}")
            self.status_label.setText(f"Error: {str(e)}")
            self.status_label.setStyleSheet("color: #FF0000; font-size: 14px;")

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
    
    def handle_midi_event(self, msg) -> None:
        """
        Handler for MIDI events from the MIDI controller.
        Delegates to handle_midi method.
        
        Args:
            msg: MIDI message to process
        """
        self.handle_midi(msg)
    
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
        
    def update_status_direct(self, color: str, message: str) -> None:
        """
        Update the status label directly with the specified color and message.
        
        Args:
            color: CSS color string
            message: Status message to display
        """
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {color}; font-size: 14px;")

    def load_default_bank(self) -> None:
        """Auto-load the default bank specified during initialization."""
        LOG.info(f"Auto-loading default bank: {self.default_bank}")
        # Find the index of the default bank in the dropdown
        index = self.bank_dropdown.findText(self.default_bank)
        if index >= 0:
            self.bank_dropdown.setCurrentIndex(index)
            # The bank_changed signal handler will take care of loading the bank
        else:
            LOG.warning(f"Default bank '{self.default_bank}' not found in bank list")

    def check_synth_connectivity(self) -> None:
        """Check if all synth voices are connected and update the UI accordingly."""
        if not self.current_bank:
            return
            
        # Get total synth count
        total_synths = len(self.synth_processes)
        if total_synths == 0:
            return
            
        # Count alive processes
        alive_count = sum(1 for p in self.synth_processes if p.poll() is None)
        
        LOG.info(f"Synth connectivity check: {alive_count}/{total_synths} synths connected")
        
        # Update UI based on connectivity
        if alive_count == 0:
            # No synths alive
            self.update_status_direct("#FF0000", f"WARNING: No synths connected (0/{total_synths})")
        elif alive_count < total_synths:
            # Some synths alive
            self.update_status_direct("#FFAA00", f"Partial connection: {alive_count}/{total_synths} synths")
        else:
            # All synths alive
            self.update_status_direct("#00FF00", f"Connected: {alive_count}/{total_synths} synths")

    def update_button_state(self, enabled: bool) -> None:
        """
        Enable or disable the bank and patch buttons based on bank selection state.
        
        Args:
            enabled: Whether buttons should be enabled
        """
        for button in [self.load_patch_btn, self.save_patch_btn, self.panic_btn]:
            button.setEnabled(enabled) 
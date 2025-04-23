"""
GUI for the MIDI-OSC bridge.

The visual control center for the Caelus system - where humans meet the machine.
"""
import os
import time
import yaml
import threading
from typing import Dict, List, Optional, Any, Union, Callable, Tuple
import subprocess
import mido
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QFrame, QFileDialog, QMessageBox
)
from PyQt6.QtCore import QTimer, pyqtSignal as Signal, QObject
from pythonosc import udp_client
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer

from lib.common.utils import LOG
from lib.midi_osc.midi_worker import MidiWorker
from lib.midi_osc.helpers import (
    kill_all_processes, monitor_process_output, 
    send_osc, active_processes
)

# Signal to allow OSC server to communicate with GUI
class OSCSignalHandler(QObject):
    """Handler for OSC signals that communicates with the GUI."""
    status_updated = Signal(str, str)
    param_changed = Signal(str, float)

# Signal handler for thread-safe UI updates
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
        LOG.info(f"Received wildcard OSC message: {address} {args}")
        if not address.startswith('/ui/'):
            LOG.debug(f"Received unhandled OSC: {address} {args}")
    
    def run(self) -> None:
        """Run the OSC server in a separate thread."""
        try:
            self.server = ThreadingOSCUDPServer(("127.0.0.1", self.listen_port), self.dispatcher)
            LOG.info(f"OSC server listening on 127.0.0.1:{self.listen_port}")
            
            # Modified serve_forever loop that can be stopped
            count: int = 0
            last_log: float = time.time()
            while self.running:
                # Handle any incoming message
                self.server.handle_request()
                
                # Log a heartbeat message occasionally to show we're still listening
                count += 1
                if count % 100 == 0 or time.time() - last_log > 10:
                    LOG.info(f"OSC server still listening on 127.0.0.1:{self.listen_port}...")
                    last_log = time.time()
                    
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

class MidiOscGui(QWidget):
    """
    Main GUI for the MIDI-OSC bridge.
    
    Provides the user interface for selecting MIDI devices,
    managing synth banks, and controlling the router.
    """
    def __init__(
        self, 
        osc_ip: str = "127.0.0.1", 
        osc_port: int = 9001, 
        router_name: str = "router", 
        presets_dir: str = "presets", 
        ui_osc_port: int = 9002
    ) -> None:
        """
        Initialize the MIDI-OSC bridge GUI.
        
        Args:
            osc_ip: IP address of the OSC router
            osc_port: Port of the OSC router
            router_name: Name of the OSC router
            presets_dir: Directory containing synth presets
            ui_osc_port: Port to listen on for UI feedback
        """
        super().__init__()
        self.osc_ip: str = osc_ip
        self.osc_port: int = osc_port
        self.router_name: str = router_name
        self.presets_dir: str = presets_dir
        self.ui_osc_port: int = ui_osc_port
        
        # MIDI worker and process tracking
        self.midi_worker: Optional[MidiWorker] = None
        self.synth_processes: List[subprocess.Popen] = []
        self.midi_in_port: Optional[str] = None
        self.current_bank: Optional[str] = None
        self.light_timer: Optional[QTimer] = None
        
        # Set up UI signal handler for thread-safe updates
        self.ui_signal_handler = UISignalHandler()
        self.ui_signal_handler.midi_light_update.connect(self.update_midi_light)
        self.ui_signal_handler.osc_light_update.connect(self.update_osc_light)
        self.ui_signal_handler.status_update.connect(self.update_status_direct)
        
        # Create OSC client
        self.osc_client: udp_client.SimpleUDPClient = udp_client.SimpleUDPClient(self.osc_ip, self.osc_port)
        
        # Set up OSC server for UI feedback
        self.osc_signal_handler: OSCSignalHandler = OSCSignalHandler()
        self.osc_signal_handler.status_updated.connect(self.update_status)
        self.osc_signal_handler.param_changed.connect(self.update_parameter)
        self.osc_server: OSCServerThread = OSCServerThread(self.osc_signal_handler, listen_port=self.ui_osc_port)
        self.osc_server.start()
        
        self.setWindowTitle("Caelus MIDI↔OSC Bridge")
        self.setStyleSheet("""
            QWidget { background-color: #111; color: #FFA500; font-family: 'SF Mono', 'Menlo', 'Monaco', monospace; }
            QComboBox, QPushButton { background-color: #222; border: 1px solid #FFA500; padding: 6px; }
            QLabel { font-size: 16px; }
        """)

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
        self.worker = None
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

    def update_status(self, status_type: str, message: str) -> None:
        """
        Update status display with info from router.
        
        Args:
            status_type: Type of status message (info, warning, error, note)
            message: Status message content
        """
        # Different colors for different status types
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
        """
        Update UI elements based on parameter changes from router.
        
        Args:
            param_name: Name of the parameter that changed
            value: New parameter value
        """
        # Example implementation - could update sliders, knobs, or other controls
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
            
        # Will expand this as we add more UI controls

    def refresh_midi_ports(self) -> None:
        """Refresh the list of available MIDI input ports."""
        self.midi_dropdown.clear()
        try:
            ports = mido.get_input_names()
            LOG.info(f"Available MIDI ports: {ports}")
            
            if not ports:
                LOG.warning("WARNING: No MIDI ports found!")
                self.midi_dropdown.addItem("-- No MIDI ports found --")
                QMessageBox.warning(self, "MIDI Error", "No MIDI ports found! Please connect a MIDI device and click 'Refresh MIDI Ports'.")
            else:
                self.midi_dropdown.addItems(ports)
                # If only one port, auto-select it
                if len(ports) == 1:
                    LOG.info(f"Auto-selecting only available MIDI port: {ports[0]}")
                    # Temporarily block signals to avoid double-triggering the port change
                    self.midi_dropdown.blockSignals(True)
                    self.midi_dropdown.setCurrentIndex(0)
                    self.midi_dropdown.blockSignals(False)
                    # Manually trigger the port change
                    self.midi_port_changed(0)
                    
        except Exception as e:
            LOG.error(f"ERROR listing MIDI ports: {e}")
            self.midi_dropdown.addItem("-- Error listing MIDI ports --")
            QMessageBox.critical(self, "MIDI Error", f"Failed to list MIDI ports: {str(e)}")
            import traceback
            traceback.print_exc()

    def refresh_bank_list(self) -> None:
        """Refresh the list of available synth banks from the presets directory."""
        self.bank_dropdown.clear()
        try:
            # Add empty selection at the beginning
            self.bank_dropdown.addItem("-- Select Synth --")
            
            # Get list of directories in presets folder
            if os.path.exists(self.presets_dir):
                banks = [d for d in os.listdir(self.presets_dir) 
                         if os.path.isdir(os.path.join(self.presets_dir, d)) and d != "__pycache__"]
                self.bank_dropdown.addItems(banks)
        except Exception as e:
            LOG.error(f"Error loading banks: {e}")

    def update_midi_ports(self) -> None:
        """Periodically update the list of MIDI ports if they've changed."""
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
            # Test if we can open the port
            LOG.info(f"Testing MIDI port: {port_name}")
            test_port = mido.open_input(port_name)
            test_port.close()
            LOG.info("MIDI port test successful")
            
            # Create the worker
            self.midi_worker = MidiWorker(port_name, self.handle_midi)
            self.midi_worker.start()
            LOG.info(f"Started MIDI worker for port: {port_name}")
        except Exception as e:
            LOG.error(f"ERROR connecting to MIDI port: {e}")
            QMessageBox.warning(self, "MIDI Error", f"Failed to connect to MIDI port: {str(e)}")
            self.midi_worker = None

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
            self.load_bank()  # Use load_bank instead of load_synth_bank directly

    def load_synth_bank(self, bank_name: str) -> bool:
        """
        Load a synth bank, starting the router and synth instances.
        
        Args:
            bank_name: Name of the bank to load
            
        Returns:
            True if bank was loaded successfully, False otherwise
        """
        try:
            LOG.info(f"Starting to load synth bank: {bank_name}")
            
            # Stop any existing synths
            kill_all_processes()
            
            self.current_bank = bank_name
            bank_dir = os.path.join(self.presets_dir, bank_name)
            LOG.info(f"Loading synth bank: {bank_name} from {bank_dir}")
            
            # Validate bank directory
            if not os.path.exists(bank_dir):
                error_msg = f"Bank directory {bank_dir} does not exist"
                LOG.error(error_msg)
                raise FileNotFoundError(error_msg)
            
            # Check for required files
            voices_file = os.path.join(bank_dir, "voices.yaml")
            if not os.path.exists(voices_file):
                error_msg = f"Missing voices.yaml in {bank_dir}"
                LOG.error(error_msg)
                raise FileNotFoundError(error_msg)
                
            synth_file = os.path.join(bank_dir, "synth")
            if not os.path.exists(synth_file):
                error_msg = f"Missing synth binary/script in {bank_dir}"
                LOG.error(error_msg)
                raise FileNotFoundError(error_msg)
            
            # Make synth file executable
            LOG.info(f"Making synth file executable: {synth_file}")
            os.chmod(synth_file, 0o755)
            
            # Tell the router where to send UI updates
            ui_osc_host = self.osc_ip
            ui_osc_port = self.ui_osc_port
            
            # Read voices config to get ports for synth instances
            with open(voices_file, 'r') as f:
                config = yaml.safe_load(f)
                LOG.info(f"Loaded voices config: {config}")
            
            # Get default host from settings
            default_host = "127.0.0.1"
            if 'settings' in config and 'synth_host' in config['settings']:
                default_host = config['settings']['synth_host']
            
            # Step 1: Process remote synth connections first
            # This helps identify network issues before starting the router
            LOG.info("Checking remote synth connections...")
            remote_voice_count = 0
            remote_voices_status = {}
            
            import socket
            for voice in config.get('voices', []):
                host = voice.get('host', default_host)
                port = voice.get('port')
                voice_id = voice.get('id', f"voice_{port}")
                
                if host not in ("127.0.0.1", "localhost"):
                    # Test connection to remote synth
                    LOG.info(f"Testing connection to remote synth at {host}:{port}")
                    try:
                        # Simple socket test to see if port is open
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(2)  # 2 second timeout
                        result = sock.connect_ex((host, port))
                        sock.close()
                        
                        if result == 0:
                            LOG.info(f"Connection to remote synth at {host}:{port} successful")
                            remote_voice_count += 1
                            remote_voices_status[voice_id] = "connected"
                        else:
                            LOG.warning(f"Connection to remote synth at {host}:{port} failed (port not open)")
                            remote_voices_status[voice_id] = "failed"
                    except Exception as e:
                        LOG.error(f"Error testing connection to remote synth at {host}:{port}: {e}")
                        remote_voices_status[voice_id] = "error"
            
            if remote_voice_count > 0:
                LOG.info(f"Successfully connected to {remote_voice_count} remote synth instances")
            else:
                LOG.info("No remote synths configured or connected")
                
            # Step 2: Launch OSC router with UI feedback address
            LOG.info(f"Starting OSC router with config: {voices_file}")
            router_cmd = [
                "python3", "osc_router.py",
                "-c", voices_file,
                "-p", str(self.osc_port),
                "--ui-host", ui_osc_host,
                "--ui-port", str(ui_osc_port)
            ]
            cmd_str = ' '.join(router_cmd)
            LOG.info(f"Router command: {cmd_str}")
            LOG.info(f"UI feedback will be sent to {ui_osc_host}:{ui_osc_port}")
            
            # Check if osc_router.py has the --ui-host and --ui-port parameters
            try:
                import subprocess
                check_cmd = ["python3", "osc_router.py", "--help"]
                help_output = subprocess.check_output(check_cmd, universal_newlines=True)
                if "--ui-host" not in help_output or "--ui-port" not in help_output:
                    LOG.warning("WARNING: osc_router.py doesn't have UI parameters. Router updates will not work!")
                    LOG.warning("Please update osc_router.py to include --ui-host and --ui-port parameters")
            except Exception as e:
                LOG.warning(f"Could not check osc_router.py parameters: {e}")
            
            # Use a non-blocking approach to capture and monitor output
            router_proc = subprocess.Popen(
                router_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,  # Text mode for output
                bufsize=1  # Line buffered
            )
            active_processes.append(router_proc)
            
            # Start a thread to monitor the router's output
            threading.Thread(target=monitor_process_output, 
                           args=(router_proc, "OSC ROUTER"), 
                           daemon=True).start()
            
            # Give the router time to start up
            LOG.info("Waiting for OSC router to initialize...")
            time.sleep(2)
            
            # Test OSC communication
            LOG.info("Testing OSC communication with router...")
            try:
                send_osc(self.osc_client, f"/{self.router_name}/all_notes_off", [])
                LOG.info("OSC test successful!")
            except Exception as e:
                LOG.warning(f"WARNING: OSC test failed: {e}")
            
            # Step 3: Launch local synth instances
            LOG.info(f"Launching local synth instances from: {synth_file}")
            local_voice_count = 0
            for voice in config.get('voices', []):
                host = voice.get('host', default_host)
                port = voice.get('port')
                voice_id = voice.get('id', f"voice_{port}")
                
                if host in ("127.0.0.1", "localhost"):
                    # Launch local synth
                    synth_cmd = [synth_file, "-port", str(port)]
                    LOG.info(f"Starting voice: {voice_id} on port {port}: {' '.join(synth_cmd)}")
                    synth_proc = subprocess.Popen(
                        synth_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE
                    )
                    active_processes.append(synth_proc)
                    local_voice_count += 1
                    time.sleep(0.5)  # Give each synth time to initialize
            
            LOG.info(f"Started {local_voice_count} local synth instances")
            LOG.info(f"Total voices available: {local_voice_count + remote_voice_count}")
            
            # Register with router as UI client
            LOG.info(f"Registering UI client with router: {ui_osc_host}:{ui_osc_port}")
            register_result = send_osc(self.osc_client, f"/{self.router_name}/register_ui", [ui_osc_host, ui_osc_port])
            if register_result:
                LOG.info("Successfully registered UI with router")
            else:
                LOG.error("Failed to register UI with router")
            
            # Step 4: Start UI if available
            ui_path = os.path.join(bank_dir, "ui.py")
            if os.path.exists(ui_path):
                LOG.info(f"Starting UI: {ui_path}")
                # Create environment with current directory in PYTHONPATH
                env = os.environ.copy()
                env['PYTHONPATH'] = os.getcwd() + ":" + env.get('PYTHONPATH', '')
                ui_proc = subprocess.Popen(
                    ["python3", ui_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env
                )
                active_processes.append(ui_proc)
            else:
                LOG.info(f"No UI script found at {ui_path}")
            
            # Load default patch
            default_patch = os.path.join(bank_dir, "patches", "00-Default.yaml")
            if os.path.exists(default_patch):
                LOG.info(f"Loading default patch: {default_patch}")
                self.load_patch_file(default_patch)
            
            # Enable buttons
            self.update_button_state(True)
            
            # Display status message
            status_msg = f"Bank '{bank_name}' loaded with {local_voice_count} local and {remote_voice_count} remote synths"
            self.status_label.setText(status_msg)
            self.status_label.setStyleSheet("color: #00FF00; font-size: 14px;")
            
            LOG.info(f"Successfully loaded bank: {bank_name}")
            return True
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load bank: {str(e)}")
            LOG.error(f"ERROR loading bank: {str(e)}")
            import traceback
            traceback.print_exc()
            self.update_button_state(False)
            return False

    def update_button_state(self, enabled: bool) -> None:
        """
        Update the enabled state of UI buttons.
        
        Args:
            enabled: Whether buttons should be enabled
        """
        self.load_patch_btn.setEnabled(enabled)
        self.save_patch_btn.setEnabled(enabled)
        # Always enable panic button
        self.panic_btn.setEnabled(True)
        
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
        
        try:
            with open(filename, 'w') as f:
                yaml.dump(patch_data, f, default_flow_style=False)
                
            LOG.info(f"Saved patch to {filename}")
            self.status_label.setText(f"Saved patch: {os.path.basename(filename)}")
            self.status_label.setStyleSheet("color: #00FF00; font-size: 14px;")
            
        except Exception as e:
            LOG.error(f"Error saving patch: {e}")
            self.status_label.setText(f"Error saving patch: {str(e)}")
            self.status_label.setStyleSheet("color: #FF0000; font-size: 14px;")
    
    def load_bank(self) -> None:
        """Load the currently selected synth bank."""
        bank_name = self.bank_dropdown.currentText()
        if bank_name and bank_name != "-- Select Synth --":
            LOG.info(f"Initiating load of bank: {bank_name}")
            result = self.load_synth_bank(bank_name)
            LOG.info(f"Bank loading {'succeeded' if result else 'failed'}: {bank_name}")
        else:
            LOG.warning("No valid bank selected - please select a bank first")
            QMessageBox.warning(self, "Bank Error", "Please select a synth bank first")
    
    def handle_midi(self, msg: mido.Message) -> None:
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
        
        # Stop OSC server
        if self.osc_server:
            LOG.info("Stopping OSC server")
            self.osc_server.stop()
        
        # Stop MIDI worker
        if self.midi_worker:
            LOG.info("Stopping MIDI worker")
            self.midi_worker.stop()
        
        # Kill all child processes
        LOG.info("Stopping all child processes")
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
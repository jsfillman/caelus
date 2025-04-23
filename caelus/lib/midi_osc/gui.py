"""
GUI for the MIDI-OSC bridge
"""
import os
import time
import yaml
import threading
import subprocess
import mido
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QFrame, QFileDialog, QMessageBox
)
from PyQt6.QtCore import QTimer, pyqtSignal, QObject
from pythonosc import udp_client
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer

from lib.common.utils import LOG
from lib.midi_osc.midi_worker import MidiWorker
from lib.midi_osc.helpers import (
    kill_all_processes, set_light, monitor_process_output, 
    send_osc, active_processes
)

# Signal to allow OSC server to communicate with GUI
class OSCSignalHandler(QObject):
    status_updated = pyqtSignal(str, str)
    param_changed = pyqtSignal(str, float)

class OSCServerThread(threading.Thread):
    """Thread to run OSC server in background"""
    def __init__(self, signal_handler, listen_port=9002):
        super().__init__(daemon=True)
        self.signal_handler = signal_handler
        self.listen_port = listen_port
        self.dispatcher = Dispatcher()
        self.running = True
        self.server = None
        
        # Set up handlers
        self.setup_handlers()
        
    def setup_handlers(self):
        """Set up OSC message handlers"""
        # Status message handler
        self.dispatcher.map("/ui/status", self.handle_status)
        
        # Parameter update handler
        self.dispatcher.map("/ui/param", self.handle_param_update)
        
        # Wildcard handler for debugging
        self.dispatcher.map("/*", self.handle_wildcard)
        
    def handle_status(self, address, *args):
        """Handle status messages from router"""
        LOG.info(f"Received status OSC message: {address} {args}")
        if len(args) >= 2:
            status_type = str(args[0])
            message = str(args[1])
            LOG.info(f"Received status: {status_type} - {message}")
            # Emit signal for GUI to update
            self.signal_handler.status_updated.emit(status_type, message)
            
    def handle_param_update(self, address, *args):
        """Handle parameter updates from router"""
        LOG.info(f"Received param OSC message: {address} {args}")
        if len(args) >= 2:
            param_name = str(args[0])
            value = float(args[1])
            LOG.info(f"Parameter update: {param_name} = {value}")
            # Emit signal for GUI to update
            self.signal_handler.param_changed.emit(param_name, value)
    
    def handle_wildcard(self, address, *args):
        """Debug handler for all OSC messages"""
        LOG.info(f"Received wildcard OSC message: {address} {args}")
        if not address.startswith('/ui/'):
            LOG.debug(f"Received unhandled OSC: {address} {args}")
    
    def run(self):
        """Run the OSC server"""
        try:
            self.server = ThreadingOSCUDPServer(("127.0.0.1", self.listen_port), self.dispatcher)
            LOG.info(f"OSC server listening on 127.0.0.1:{self.listen_port}")
            
            # Modified serve_forever loop that can be stopped
            count = 0
            last_log = time.time()
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
    
    def stop(self):
        """Stop the OSC server"""
        self.running = False
        if self.server:
            # Close the socket
            self.server.socket.close()
        LOG.info("OSC server stopped")

class MidiOscGui(QWidget):
    """Main GUI for the MIDI-OSC bridge"""
    def __init__(self, osc_ip="127.0.0.1", osc_port=9001, router_name="router", presets_dir="presets", ui_osc_port=9002):
        super().__init__()
        self.osc_ip = osc_ip
        self.osc_port = osc_port
        self.router_name = router_name
        self.presets_dir = presets_dir
        self.ui_osc_port = ui_osc_port
        
        # Create OSC client
        self.osc = udp_client.SimpleUDPClient(self.osc_ip, self.osc_port)
        
        # Set up OSC server for UI feedback
        self.osc_signal_handler = OSCSignalHandler()
        self.osc_signal_handler.status_updated.connect(self.update_status)
        self.osc_signal_handler.param_changed.connect(self.update_parameter)
        self.osc_server = OSCServerThread(self.osc_signal_handler, listen_port=self.ui_osc_port)
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
            set_light(light, False)

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

    def update_status(self, status_type, message):
        """Update status display with info from router"""
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
    
    def update_parameter(self, param_name, value):
        """Update UI elements based on parameter changes from router"""
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

    def refresh_midi_ports(self):
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

    def refresh_bank_list(self):
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

    def update_midi_ports(self):
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

    def midi_port_changed(self, index):
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

    def bank_changed(self, index):
        if index <= 0:  # Skip the "-- Select Synth --" entry
            self.update_button_state(False)
            return
        
        bank_name = self.bank_dropdown.currentText()
        self.load_synth_bank(bank_name)

    def load_synth_bank(self, bank_name):
        try:
            # Stop any existing synths
            kill_all_processes()
            
            self.current_bank = bank_name
            bank_dir = os.path.join(self.presets_dir, bank_name)
            LOG.info(f"Loading synth bank: {bank_name} from {bank_dir}")
            
            # Validate bank directory
            if not os.path.exists(bank_dir):
                raise FileNotFoundError(f"Bank directory {bank_dir} does not exist")
            
            # Check for required files
            voices_file = os.path.join(bank_dir, "voices.yaml")
            if not os.path.exists(voices_file):
                raise FileNotFoundError(f"Missing voices.yaml in {bank_dir}")
                
            synth_file = os.path.join(bank_dir, "synth")
            if not os.path.exists(synth_file):
                raise FileNotFoundError(f"Missing synth binary/script in {bank_dir}")
            
            # Make synth file executable
            os.chmod(synth_file, 0o755)
            
            # Tell the router where to send UI updates
            ui_osc_host = self.osc_ip
            ui_osc_port = self.ui_osc_port
            
            # Launch OSC router with UI feedback address
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
                send_osc(self.osc, f"/{self.router_name}/all_notes_off", [])
                LOG.info("OSC test successful!")
            except Exception as e:
                LOG.warning(f"WARNING: OSC test failed: {e}")
            
            # Read voices config to get ports for synth instances
            with open(voices_file, 'r') as f:
                config = yaml.safe_load(f)
                LOG.info(f"Loaded voices config: {config}")
            
            # Get default host from settings
            default_host = "127.0.0.1"
            if 'settings' in config and 'synth_host' in config['settings']:
                default_host = config['settings']['synth_host']
            
            # Launch synth instances for local hosts
            LOG.info(f"Launching synth instances from: {synth_file}")
            voice_count = 0
            for voice in config.get('voices', []):
                host = voice.get('host', default_host)
                port = voice.get('port')
                
                if host in ("127.0.0.1", "localhost"):
                    # Launch local synth
                    synth_cmd = [synth_file, "-port", str(port)]
                    LOG.info(f"Starting voice: {voice.get('id')} on port {port}: {' '.join(synth_cmd)}")
                    synth_proc = subprocess.Popen(
                        synth_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE
                    )
                    active_processes.append(synth_proc)
                    voice_count += 1
                    time.sleep(0.5)  # Give each synth time to initialize
            
            LOG.info(f"Started {voice_count} synth instances")
            
            # Register with router as UI client
            LOG.info(f"Registering UI client with router: {ui_osc_host}:{ui_osc_port}")
            register_result = send_osc(self.osc, f"/{self.router_name}/register_ui", [ui_osc_host, ui_osc_port])
            if register_result:
                LOG.info("Successfully registered UI with router")
            else:
                LOG.error("Failed to register UI with router")
            
            # Start UI
            ui_path = os.path.join(bank_dir, "ui.py")
            if os.path.exists(ui_path):
                LOG.info(f"Starting UI: {ui_path}")
                ui_proc = subprocess.Popen(
                    ["python3", ui_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
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
            
            LOG.info(f"Successfully loaded bank: {bank_name}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load bank: {str(e)}")
            LOG.error(f"ERROR loading bank: {str(e)}")
            import traceback
            traceback.print_exc()
            self.update_button_state(False)

    def update_button_state(self, enabled):
        self.load_patch_btn.setEnabled(enabled)
        self.save_patch_btn.setEnabled(enabled)
        # Always enable panic button
        self.panic_btn.setEnabled(True)
        
    def load_patch_file(self, patch_file):
        try:
            if not os.path.exists(patch_file):
                raise FileNotFoundError(f"Patch file {patch_file} not found")
                
            LOG.info(f"Loading patch from: {patch_file}")
            with open(patch_file, 'r') as f:
                patch_data = yaml.safe_load(f)
            
            # Send patch parameters to synth via OSC
            if isinstance(patch_data, dict):
                LOG.info(f"Sending {len(patch_data)} parameters:")
                for param, value in patch_data.items():
                    # Send to all synth instances
                    # Note: The param_all endpoint expects [param_name, value] format
                    osc_address = f"/{self.router_name}/param_all"
                    LOG.info(f"  {param}: {value} -> {osc_address}")
                    send_osc(self.osc, osc_address, [param, value])
                    
            self.current_patch = os.path.basename(patch_file)
            LOG.info(f"Loaded patch: {self.current_patch}")
            
        except Exception as e:
            QMessageBox.warning(self, "Load Error", f"Failed to load patch: {str(e)}")
            LOG.error(f"ERROR loading patch: {str(e)}")
            import traceback
            traceback.print_exc()

    def load_patch(self):
        if not self.current_bank:
            return
            
        patches_dir = os.path.join(self.presets_dir, self.current_bank, "patches")
        if not os.path.exists(patches_dir):
            QMessageBox.warning(self, "Error", f"Patches directory not found: {patches_dir}")
            return
            
        file_dialog = QFileDialog(self)
        file_dialog.setDirectory(patches_dir)
        file_dialog.setNameFilter("YAML files (*.yaml)")
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        
        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                self.load_patch_file(selected_files[0])

    def save_patch(self):
        if not self.current_bank:
            return
        
        # Request all current parameters from the router
        # This is a simplification - in real implementation you'd need to
        # query the actual parameters from the synth
        
        # For demo purposes, create sample patch data
        patch_data = {
            "cutoff": 1000,
            "resonance": 0.5,
            "attack": 0.01,
            "decay": 0.2,
            "sustain": 0.7,
            "release": 0.5
        }
        
        patches_dir = os.path.join(self.presets_dir, self.current_bank, "patches")
        if not os.path.exists(patches_dir):
            os.makedirs(patches_dir)
            
        file_dialog = QFileDialog(self)
        file_dialog.setDirectory(patches_dir)
        file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        file_dialog.setNameFilter("YAML files (*.yaml)")
        file_dialog.setDefaultSuffix("yaml")
        
        if file_dialog.exec():
            selected_file = file_dialog.selectedFiles()[0]
            if selected_file:
                try:
                    with open(selected_file, 'w') as f:
                        yaml.dump(patch_data, f, default_flow_style=False)
                    self.current_patch = os.path.basename(selected_file)
                    LOG.info(f"Saved patch: {self.current_patch}")
                except Exception as e:
                    QMessageBox.critical(self, "Save Error", f"Failed to save patch: {str(e)}")

    def load_bank(self):
        self.bank_dropdown.showPopup()

    def handle_midi(self, msg):
        LOG.info(f"MIDI: {msg}")
        self.midi_recent = True
        address = f"/{self.router_name}/unknown"
        val = 0.0
        if msg.type == 'note_on':
            # Note: Some MIDI controllers send note-on with velocity 0 instead of note-off
            if msg.velocity == 0:
                # This is actually a note-off
                address = f"/{self.router_name}/note_off"
                val = [msg.note]
            else:
                address = f"/{self.router_name}/note_on"
                val = [msg.note, msg.velocity / 127.0]
                LOG.info(f"Sending note_on to router: note={msg.note}, velocity={msg.velocity/127.0}")
        elif msg.type == 'note_off':
            address = f"/{self.router_name}/note_off"
            val = [msg.note]
            LOG.info(f"Sending note_off to router: note={msg.note}")
        elif msg.type == 'control_change':
            address = f"/{self.router_name}/cc"
            val = [msg.control, msg.value / 127.0]
            LOG.info(f"Sending CC to router: cc={msg.control}, value={msg.value/127.0}")
            
            # Handle sustain pedal (CC64) specially for debugging
            if msg.control == 64:
                sustain_on = msg.value >= 64
                LOG.info(f"Sustain pedal {'ON' if sustain_on else 'OFF'} - value: {msg.value}")
                
        elif msg.type == 'polytouch':
            address = f"/{self.router_name}/poly_aftertouch"
            val = [msg.note, msg.value / 127.0]
        elif msg.type == 'pitchwheel':
            address = f"/{self.router_name}/pitch_bend"
            # Pitchwheel range is -8192 to 8191, normalize to -1.0 to 1.0
            val = [msg.pitch / 8192.0]
        
        if send_osc(self.osc, address, val):
            self.osc_recent = True
            LOG.info(f"Successfully sent OSC message: {address} {val}")
        else:
            LOG.error(f"Failed to send OSC message: {address} {val}")

    def dim_lights(self):
        set_light(self.midi_light, self.midi_recent)
        set_light(self.osc_light, self.osc_recent)
        self.midi_recent = False
        self.osc_recent = False

    def closeEvent(self, event):
        """Clean up when window is closed"""
        LOG.info("Shutting down MIDI-OSC bridge...")
        
        # Stop MIDI worker
        if self.worker:
            LOG.info("Stopping MIDI worker...")
            self.worker.stop()
        
        # Stop OSC server
        if self.osc_server:
            LOG.info("Stopping OSC server...")
            self.osc_server.stop()
        
        # Kill all child processes
        LOG.info(f"Terminating {len(active_processes)} child processes...")
        for proc in active_processes[:]:  # Create a copy of the list to avoid modification during iteration
            try:
                LOG.info(f"Terminating process {proc.pid}...")
                proc.terminate()
                proc.wait(timeout=1.0)  # Wait up to 1 second for clean termination
            except Exception as e:
                LOG.error(f"Error terminating process: {e}")
                # Force kill if terminate doesn't work
                try:
                    import signal
                    import os
                    os.kill(proc.pid, signal.SIGKILL)
                    LOG.info(f"Force killed process {proc.pid}")
                except Exception as e2:
                    LOG.error(f"Error force killing process: {e2}")
        
        # Call the general kill function as backup
        kill_all_processes()
        
        # Clear the process list
        active_processes.clear()
        
        LOG.info("Shutdown complete")
        event.accept()

    def panic(self):
        """Emergency function to clear all stuck notes and reset synths"""
        LOG.info("PANIC button pressed - clearing all notes")
        
        # Send all notes off message
        send_osc(self.osc, f"/{self.router_name}/all_notes_off", [])
        
        # Also send direct note-offs for all possible notes (0-127)
        for note in range(128):
            send_osc(self.osc, f"/{self.router_name}/note_off", [note])
        
        # Set sustain pedal off
        send_osc(self.osc, f"/{self.router_name}/cc", [64, 0.0])
        
        # Reset all voices
        for voice_idx in range(16):  # Assuming max 16 voices
            send_osc(self.osc, f"/{self.router_name}/voice/reset", voice_idx)
        
        # Update GUI state
        self.midi_recent = False
        self.osc_recent = False
        self.dim_lights()
        
        QMessageBox.information(self, "Panic", "All notes have been cleared and voices reset.") 
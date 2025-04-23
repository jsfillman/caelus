import sys
import time
import mido
import threading
import os
import yaml
import json
import subprocess
import signal
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QFrame, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPalette
from pythonosc import udp_client
import argparse

# --- Configuration ---
OSC_IP = "127.0.0.1"  # Use localhost instead of 0.0.0.0
OSC_PORT = 9001  # Changed from 9000 to avoid conflicts
ROUTER_NAME = "router"
PRESETS_DIR = "presets"
osc = udp_client.SimpleUDPClient(OSC_IP, OSC_PORT)

# --- Handle OSC messages ---
def send_osc(address, value):
    try:
        print(f"Sending OSC: {address} {value}")
        osc.send_message(address, value)
        return True
    except Exception as e:
        print(f"ERROR sending OSC message: {e}")
        return False

# --- Process Management ---
active_processes = []

def kill_process(proc):
    if proc and proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
        except Exception as e:
            print(f"Error killing process: {e}")

def kill_all_processes():
    global active_processes
    print(f"Stopping {len(active_processes)} active processes...")
    for proc in active_processes:
        kill_process(proc)
    active_processes = []
    print("All processes stopped")

# --- MIDI Light Helper ---
def set_light(label, on):
    color = "#FFA500" if on else "#333"
    label.setStyleSheet(f"""
        background-color: {color};
        border-radius: 15px;
        border: 2px solid #FFA500;
    """)
    label.repaint()
    
# --- MIDI Worker Thread ---
class MidiWorker(threading.Thread):
    def __init__(self, port_name, midi_callback):
        super().__init__(daemon=True)
        self.port_name = port_name
        self.running = True
        self.midi_callback = midi_callback
        self.inport = None

    def run(self):
        try:
            print(f"Opening MIDI port: {self.port_name}")
            # Keep the port object as an instance variable
            self.inport = mido.open_input(self.port_name)
            print(f"MIDI port opened successfully: {self.port_name}")
            print("Waiting for MIDI messages... (play some notes)")
            
            # Main message processing loop
            while self.running:
                # Process all pending messages
                for msg in self.inport.iter_pending():
                    try:
                        self.midi_callback(msg)
                    except Exception as e:
                        print(f"Error processing MIDI message: {e}")
                # Brief sleep to prevent CPU hogging
                time.sleep(0.001)  # Use a shorter sleep time for better responsiveness
                
        except Exception as e:
            print(f"ERROR in MIDI thread: {e}")
            print("Available MIDI ports:", mido.get_input_names())
            import traceback
            traceback.print_exc()
        finally:
            # Always close the port when done
            if self.inport:
                print(f"Closing MIDI port: {self.port_name}")
                self.inport.close()

    def stop(self):
        self.running = False
        # Give the thread a moment to clean up
        time.sleep(0.1)
        # Force close the port if it's still open
        if self.inport:
            try:
                self.inport.close()
            except Exception:
                pass

# --- Main GUI ---
class MidiOscGui(QWidget):
    def __init__(self):
        super().__init__()
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
        
        # Initially disable buttons until a bank is selected
        self.update_button_state(False)
        
        for button in [self.load_bank_btn, self.load_patch_btn, self.save_patch_btn]:
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

    def refresh_midi_ports(self):
        self.midi_dropdown.clear()
        try:
            ports = mido.get_input_names()
            print(f"Available MIDI ports: {ports}")
            
            if not ports:
                print("WARNING: No MIDI ports found!")
                self.midi_dropdown.addItem("-- No MIDI ports found --")
                QMessageBox.warning(self, "MIDI Error", "No MIDI ports found! Please connect a MIDI device and click 'Refresh MIDI Ports'.")
            else:
                self.midi_dropdown.addItems(ports)
                # If only one port, auto-select it
                if len(ports) == 1:
                    print(f"Auto-selecting only available MIDI port: {ports[0]}")
                    # Temporarily block signals to avoid double-triggering the port change
                    self.midi_dropdown.blockSignals(True)
                    self.midi_dropdown.setCurrentIndex(0)
                    self.midi_dropdown.blockSignals(False)
                    # Manually trigger the port change
                    self.midi_port_changed(0)
                    
        except Exception as e:
            print(f"ERROR listing MIDI ports: {e}")
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
            if os.path.exists(PRESETS_DIR):
                banks = [d for d in os.listdir(PRESETS_DIR) 
                         if os.path.isdir(os.path.join(PRESETS_DIR, d)) and d != "__pycache__"]
                self.bank_dropdown.addItems(banks)
        except Exception as e:
            print(f"Error loading banks: {e}")

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
            print("Stopped existing MIDI worker")
        
        if index < 0:
            print("No MIDI port selected")
            return
            
        port_name = self.midi_dropdown.currentText()
        print(f"Selected MIDI port: '{port_name}'")
        
        if "No MIDI ports found" in port_name or "Error" in port_name:
            print("Cannot connect to invalid MIDI port")
            return
            
        try:
            # Test if we can open the port
            print(f"Testing MIDI port: {port_name}")
            test_port = mido.open_input(port_name)
            test_port.close()
            print("MIDI port test successful")
            
            # Create the worker
            self.worker = MidiWorker(port_name, self.handle_midi)
            self.worker.start()
            print(f"Started MIDI worker for port: {port_name}")
        except Exception as e:
            print(f"ERROR connecting to MIDI port: {e}")
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
            bank_dir = os.path.join(PRESETS_DIR, bank_name)
            print(f"Loading synth bank: {bank_name} from {bank_dir}")
            
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
            
            # Launch OSC router
            print(f"Starting OSC router with config: {voices_file}")
            router_cmd = ["python3", "osc_router.py", "-c", voices_file, "-p", str(OSC_PORT)]
            print(f"Router command: {' '.join(router_cmd)}")
            
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
            def monitor_output(proc, name):
                while proc.poll() is None:
                    stdout_line = proc.stdout.readline()
                    if stdout_line:
                        print(f"{name} STDOUT: {stdout_line.rstrip()}")
                    stderr_line = proc.stderr.readline()
                    if stderr_line:
                        print(f"{name} STDERR: {stderr_line.rstrip()}")
                print(f"Process {name} exited with code {proc.returncode}")
            
            threading.Thread(target=monitor_output, args=(router_proc, "OSC ROUTER"), daemon=True).start()
            
            # Give the router time to start up
            print("Waiting for OSC router to initialize...")
            time.sleep(2)
            
            # Test OSC communication
            print("Testing OSC communication with router...")
            try:
                send_osc(f"/{ROUTER_NAME}/all_notes_off", [])
                print("OSC test successful!")
            except Exception as e:
                print(f"WARNING: OSC test failed: {e}")
                
            # Read voices config to get ports for synth instances
            with open(voices_file, 'r') as f:
                config = yaml.safe_load(f)
            
            # Get default host from settings
            default_host = "127.0.0.1"
            if 'settings' in config and 'synth_host' in config['settings']:
                default_host = config['settings']['synth_host']
            
            # Launch synth instances for local hosts
            print(f"Launching synth instances from: {synth_file}")
            for voice in config.get('voices', []):
                host = voice.get('host', default_host)
                port = voice.get('port')
                
                if host in ("127.0.0.1", "localhost"):
                    # Launch local synth
                    synth_cmd = [synth_file, "-port", str(port)]
                    print(f"Starting voice: {voice.get('id')} on port {port}: {' '.join(synth_cmd)}")
                    synth_proc = subprocess.Popen(
                        synth_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE
                    )
                    active_processes.append(synth_proc)
                    time.sleep(0.5)  # Give each synth time to initialize
            
            # Start UI
            ui_path = os.path.join(bank_dir, "ui.py")
            if os.path.exists(ui_path):
                print(f"Starting UI: {ui_path}")
                ui_proc = subprocess.Popen(
                    ["python3", ui_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                active_processes.append(ui_proc)
            
            # Load default patch
            default_patch = os.path.join(bank_dir, "patches", "00-Default.yaml")
            if os.path.exists(default_patch):
                print(f"Loading default patch: {default_patch}")
                self.load_patch_file(default_patch)
            
            # Enable buttons
            self.update_button_state(True)
            
            print(f"Successfully loaded bank: {bank_name}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load bank: {str(e)}")
            print(f"ERROR loading bank: {str(e)}")
            import traceback
            traceback.print_exc()
            self.update_button_state(False)

    def update_button_state(self, enabled):
        self.load_patch_btn.setEnabled(enabled)
        self.save_patch_btn.setEnabled(enabled)
        
    def load_patch_file(self, patch_file):
        try:
            if not os.path.exists(patch_file):
                raise FileNotFoundError(f"Patch file {patch_file} not found")
                
            print(f"Loading patch from: {patch_file}")
            with open(patch_file, 'r') as f:
                patch_data = yaml.safe_load(f)
            
            # Send patch parameters to synth via OSC
            if isinstance(patch_data, dict):
                print(f"Sending {len(patch_data)} parameters:")
                for param, value in patch_data.items():
                    # Send to all synth instances
                    # Note: The param_all endpoint expects [param_name, value] format
                    osc_address = f"/{ROUTER_NAME}/param_all"
                    print(f"  {param}: {value} -> {osc_address}")
                    send_osc(osc_address, [param, value])
                    
            self.current_patch = os.path.basename(patch_file)
            print(f"Loaded patch: {self.current_patch}")
            
        except Exception as e:
            QMessageBox.warning(self, "Load Error", f"Failed to load patch: {str(e)}")
            print(f"ERROR loading patch: {str(e)}")
            import traceback
            traceback.print_exc()

    def load_patch(self):
        if not self.current_bank:
            return
            
        patches_dir = os.path.join(PRESETS_DIR, self.current_bank, "patches")
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
        
        patches_dir = os.path.join(PRESETS_DIR, self.current_bank, "patches")
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
                    print(f"Saved patch: {self.current_patch}")
                except Exception as e:
                    QMessageBox.critical(self, "Save Error", f"Failed to save patch: {str(e)}")

    def load_bank(self):
        self.bank_dropdown.showPopup()

    def handle_midi(self, msg):
        print("MIDI:", msg)
        self.midi_recent = True
        address = f"/{ROUTER_NAME}/unknown"
        val = 0.0
        if msg.type == 'note_on':
            address = f"/{ROUTER_NAME}/note_on"
            val = [msg.note, msg.velocity / 127.0]
        elif msg.type == 'note_off':
            address = f"/{ROUTER_NAME}/note_off"
            val = [msg.note]
        elif msg.type == 'control_change':
            address = f"/{ROUTER_NAME}/cc"
            val = [msg.control, msg.value / 127.0]
        elif msg.type == 'polytouch':
            address = f"/{ROUTER_NAME}/poly_aftertouch"
            val = [msg.note, msg.value / 127.0]
        elif msg.type == 'pitchwheel':
            address = f"/{ROUTER_NAME}/pitch_bend"
            # Pitchwheel range is -8192 to 8191, normalize to -1.0 to 1.0
            val = [msg.pitch / 8192.0]
        
        if send_osc(address, val):
            self.osc_recent = True

    def dim_lights(self):
        set_light(self.midi_light, self.midi_recent)
        set_light(self.osc_light, self.osc_recent)
        self.midi_recent = False
        self.osc_recent = False

    def closeEvent(self, event):
        if self.worker:
            self.worker.stop()
        kill_all_processes()
        event.accept()

# --- Launch ---
if __name__ == "__main__":
    # Parse command line arguments for port
    parser = argparse.ArgumentParser(description="MIDI to OSC bridge for Caelus")
    parser.add_argument("--port", type=int, default=OSC_PORT, 
                       help=f"OSC port to use (default: {OSC_PORT})")
    args = parser.parse_args()
    
    # Override default port if specified
    if args.port != OSC_PORT:
        OSC_PORT = args.port
        print(f"Using custom OSC port: {OSC_PORT}")
        # Recreate the OSC client with the new port
        osc = udp_client.SimpleUDPClient(OSC_IP, OSC_PORT)
    
    app = QApplication(sys.argv)
    window = MidiOscGui()
    window.resize(400, 250)  # Slightly larger to accommodate the bank dropdown
    window.show()
    sys.exit(app.exec())

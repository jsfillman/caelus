import sys
import json
import logging
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDial,
    QTabWidget, QGridLayout, QSlider, QComboBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from pythonosc import udp_client, osc_message_builder
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer
import threading
import random

# --- Set up logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
LOG = logging.getLogger(__name__)

# --- OSC Setup ---
OSC_IP = "127.0.0.1"
OSC_ROUTER_PORT = 9000
OSC_UI_PORT = 9100  # Port for receiving OSC messages
osc = udp_client.SimpleUDPClient(OSC_IP, OSC_ROUTER_PORT)

# --- Main Synth UI ---
class SynthControlPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Caelus Control UI")
        self.setStyleSheet("""
            QWidget { background-color: #111; color: #FFA500; font-family: 'SF Mono', 'Menlo', monospace; }
            QDial {
                background-color: qradialgradient(cx:0.5, cy:0.5, radius:1.0, fx:0.5, fy:0.5, stop:0 #FFA500, stop:1 #111);
                border: 2px solid #FFA500;
                border-radius: 35px;
                width: 70px;
                height: 70px;
            }
            QLabel { font-size: 14px; color: #FFA500; }
            QPushButton {
                background-color: #222;
                color: #FFA500;
                border: 1px solid #FFA500;
                padding: 6px;
            }
            QTabWidget::pane {
                border: 1px solid #FFA500;
                background: #222;
            }
            QTabWidget::tab-bar {
                left: 5px;
            }
            QTabBar::tab {
                background: #222;
                border: 1px solid #FFA500;
                padding: 5px;
                color: #FFA500;
            }
            QTabBar::tab:selected {
                background: #333;
            }
            QSlider::groove:horizontal {
                border: 1px solid #999999;
                height: 8px;
                background: #222;
                margin: 2px 0;
            }
            QSlider::handle:horizontal {
                background: #FFA500;
                border: 1px solid #5c5c5c;
                width: 18px;
                margin: -2px 0;
                border-radius: 3px;
            }
            QComboBox {
                background-color: #222;
                color: #FFA500;
                border: 1px solid #FFA500;
                padding: 5px;
            }
        """)

        # Setup tabs
        self.tabs = QTabWidget()
        self.router_tab = QWidget()
        self.synth_tab = QWidget()
        self.voices_tab = QWidget()
        
        self.tabs.addTab(self.router_tab, "Router")
        self.tabs.addTab(self.synth_tab, "Synth")
        self.tabs.addTab(self.voices_tab, "Voices")
        
        # Create layouts for each tab
        self.setup_router_tab()
        self.setup_synth_tab()
        self.setup_voices_tab()
        
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.tabs)
        self.setLayout(main_layout)
        
        # Start OSC listener for feedback
        self.setup_osc_listener()
        
        # Add timer to refresh UI periodically
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_ui)
        self.refresh_timer.start(1000)  # Refresh every second
    
    def setup_router_tab(self):
        """Setup the router control tab"""
        layout = QGridLayout()
        
        # Router info section
        row = 0
        layout.addWidget(QLabel("Router Settings"), row, 0, 1, 2)
        
        # Synth Name
        row += 1
        layout.addWidget(QLabel("Synth Name:"), row, 0)
        self.synth_name_combo = QComboBox()
        self.synth_name_combo.addItems(["simple", "complex", "fm", "wavetable"])
        self.synth_name_combo.currentTextChanged.connect(self.on_synth_name_changed)
        layout.addWidget(self.synth_name_combo, row, 1)
        
        # Default Cutoff
        row += 1
        layout.addWidget(QLabel("Default Cutoff:"), row, 0)
        self.cutoff_slider = QSlider(Qt.Orientation.Horizontal)
        self.cutoff_slider.setRange(20, 20000)
        self.cutoff_slider.setValue(1000)
        self.cutoff_slider.setTracking(False)
        self.cutoff_slider.valueChanged.connect(self.on_cutoff_changed)
        layout.addWidget(self.cutoff_slider, row, 1)
        self.cutoff_label = QLabel("1000 Hz")
        layout.addWidget(self.cutoff_label, row, 2)
        
        # All Notes Off button
        row += 1
        all_notes_off_btn = QPushButton("All Notes Off")
        all_notes_off_btn.clicked.connect(self.all_notes_off)
        layout.addWidget(all_notes_off_btn, row, 0, 1, 2)
        
        # Status section
        row += 1
        layout.addWidget(QLabel("Status"), row, 0, 1, 2)
        
        # Active Notes
        row += 1
        layout.addWidget(QLabel("Active Notes:"), row, 0)
        self.active_notes_label = QLabel("None")
        layout.addWidget(self.active_notes_label, row, 1)
        
        # Sustained Notes
        row += 1
        layout.addWidget(QLabel("Sustained Notes:"), row, 0)
        self.sustained_notes_label = QLabel("None")
        layout.addWidget(self.sustained_notes_label, row, 1)
        
        # Voice Count
        row += 1
        layout.addWidget(QLabel("Voice Count:"), row, 0)
        self.voice_count_label = QLabel("0")
        layout.addWidget(self.voice_count_label, row, 1)
        
        # Set the layout
        self.router_tab.setLayout(layout)
    
    def setup_synth_tab(self):
        """Setup the synth parameters tab"""
        try:
            # Load synth definition if available
            with open("simple.dsp.json") as f:
                synth_ui = json.load(f)
            
            layout = QVBoxLayout()
            
            # Process UI definition
            for group in synth_ui.get("ui", []):
                for item in group.get("items", []):
                    ctrl_type = item["type"]
                    label = item.get("label")
                    address = item.get("meta", [{}])[0].get("osc", item.get("address"))
                    
                    # Skip gate and freq controls
                    if label in ["gate", "freq"]:
                        continue
                    
                    if ctrl_type == "hslider":
                        self.add_dial(layout, label, address, item["init"], item["min"], item["max"])
                    elif ctrl_type == "button":
                        self.add_button(layout, label, address)
        except Exception as e:
            # If no synth definition, create some default controls
            layout = QVBoxLayout()
            layout.addWidget(QLabel(f"Error loading synth definition: {e}"))
            layout.addWidget(QLabel("Using default controls"))
            
            # Add some default controls
            self.add_dial(layout, "Gain", "/gain", 0.5, 0.0, 1.0)
            self.add_dial(layout, "Attack", "/attack", 0.01, 0.001, 1.0)
            self.add_dial(layout, "Release", "/release", 0.5, 0.001, 2.0)
            self.add_dial(layout, "Cutoff", "/cutoff", 1000, 20, 20000)
            self.add_dial(layout, "Resonance", "/resonance", 0.5, 0.0, 1.0)
        
        self.synth_tab.setLayout(layout)
    
    def setup_voices_tab(self):
        """Setup the voices control tab"""
        layout = QVBoxLayout()
        
        # Get voice count
        osc.send_message("/router/get", "router/voices")
        
        # Create a placeholder - we'll populate this dynamically when we get data
        self.voices_layout = QGridLayout()
        voice_container = QWidget()
        voice_container.setLayout(self.voices_layout)
        
        layout.addWidget(QLabel("Voice Status"))
        layout.addWidget(voice_container)
        
        self.voices_tab.setLayout(layout)
    
    def setup_voice_controls(self, voice_count):
        """Setup voice status displays"""
        # Clear existing widgets
        for i in reversed(range(self.voices_layout.count())): 
            self.voices_layout.itemAt(i).widget().setParent(None)
        
        # Create headers
        self.voices_layout.addWidget(QLabel("Voice"), 0, 0)
        self.voices_layout.addWidget(QLabel("Note"), 0, 1)
        self.voices_layout.addWidget(QLabel("Active"), 0, 2)
        self.voices_layout.addWidget(QLabel("Reset"), 0, 3)
        
        # Create voice status rows
        self.voice_status_labels = []
        self.voice_note_labels = []
        self.voice_active_labels = []
        
        for i in range(voice_count):
            # Voice ID
            self.voices_layout.addWidget(QLabel(f"{i}"), i+1, 0)
            
            # Note
            note_label = QLabel("-")
            self.voice_note_labels.append(note_label)
            self.voices_layout.addWidget(note_label, i+1, 1)
            
            # Active status
            active_label = QLabel("No")
            self.voice_active_labels.append(active_label)
            self.voices_layout.addWidget(active_label, i+1, 2)
            
            # Reset button
            reset_btn = QPushButton("Reset")
            reset_btn.clicked.connect(lambda checked, idx=i: self.reset_voice(idx))
            self.voices_layout.addWidget(reset_btn, i+1, 3)
    
    def add_dial(self, layout, name, address, init, min_val, max_val):
        """Add a control dial to the UI"""
        container = QVBoxLayout()
        label = QLabel(name)
        label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        
        # Create value label
        value_label = QLabel(f"{init}")
        value_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        
        dial = QDial()
        dial.setMinimum(0)
        dial.setMaximum(1000)
        dial.setValue(int((init - min_val) / (max_val - min_val) * 1000))
        
        # Store min/max for scaling
        dial.min_val = min_val
        dial.max_val = max_val
        dial.address = address
        dial.value_label = value_label
        
        dial.valueChanged.connect(
            lambda val, dial=dial: self.on_dial_changed(dial, val)
        )
        
        container.addWidget(label)
        container.addWidget(dial, alignment=Qt.AlignmentFlag.AlignHCenter)
        container.addWidget(value_label)
        
        layout.addLayout(container)
    
    def on_dial_changed(self, dial, val):
        """Handle dial value changes"""
        # Scale value from 0-1000 to min-max
        scaled_val = dial.min_val + (val / 1000) * (dial.max_val - dial.min_val)
        
        # Update label
        if dial.max_val >= 100:
            # Format large numbers without decimal places
            dial.value_label.setText(f"{int(scaled_val)}")
        else:
            # Format small numbers with 2 decimal places
            dial.value_label.setText(f"{scaled_val:.2f}")
        
        # Send to all voices via router
        self.send_to_all_voices(dial.address, scaled_val)
    
    def add_button(self, layout, name, address):
        """Add a button control to the UI"""
        button = QPushButton(name)
        button.setCheckable(True)
        button.clicked.connect(lambda checked, a=address: self.send_to_all_voices(a, 1.0 if checked else 0.0))
        layout.addWidget(button)
    
    def on_synth_name_changed(self, name):
        """Handle synth name changes"""
        osc.send_message("/router/synth_name", name)
    
    def on_cutoff_changed(self, value):
        """Handle cutoff slider changes"""
        osc.send_message("/router/default_cutoff", float(value))
        self.cutoff_label.setText(f"{value} Hz")
    
    def all_notes_off(self):
        """Send all notes off message"""
        # This will be handled by a special OSC endpoint in the router
        osc.send_message("/router/all_notes_off", 1)
    
    def reset_voice(self, voice_idx):
        """Reset a specific voice"""
        # Send the voice index as an argument
        osc.send_message("/router/voice/reset", int(voice_idx))
    
    def send_to_all_voices(self, path, value):
        """Send a parameter to all active voices"""
        if not path.startswith("/"):
            path = "/" + path
        
        # Send directly to the parameter path
        LOG.info(f"Sending parameter {path} = {value}")
        osc.send_message(path, float(value))
    
    def setup_osc_listener(self):
        """Setup OSC listener for feedback from the router"""
        self.dispatcher = Dispatcher()
        # Add handler for router value responses
        self.dispatcher.map("/router/value/*", self.handle_router_value)
        
        # Start the OSC server
        try:
            self.server = BlockingOSCUDPServer(("127.0.0.1", OSC_UI_PORT), self.dispatcher)
            server_thread = threading.Thread(target=self.server.serve_forever)
            server_thread.daemon = True
            server_thread.start()
            print(f"OSC listening on port {OSC_UI_PORT}")
        except Exception as e:
            print(f"Error starting OSC server: {e}")
    
    def handle_router_value(self, address, *args):
        """Handle value responses from the router"""
        if len(args) < 1:
            return
            
        # Parse the address to determine what to update
        parts = address.split('/')
        if len(parts) < 4:
            return
            
        var_path = '/'.join(parts[3:])
        value = args[0]
        
        # Update UI based on received values
        if var_path == "voice_manager/active_notes":
            try:
                notes = json.loads(value)
                self.active_notes_label.setText(", ".join(map(str, notes)) if notes else "None")
            except:
                self.active_notes_label.setText(str(value))
                
        elif var_path == "voice_manager/sustained_notes":
            try:
                notes = json.loads(value)
                self.sustained_notes_label.setText(", ".join(map(str, notes)) if notes else "None")
            except:
                self.sustained_notes_label.setText(str(value))
                
        elif var_path == "router/voices":
            self.voice_count_label.setText(str(value))
            # Setup voice controls based on count
            self.setup_voice_controls(int(value))
            
        # Handle voice status updates
        elif var_path.startswith("voice/") and var_path.endswith("/note"):
            try:
                parts = var_path.split('/')
                if len(parts) >= 3:
                    voice_idx = int(parts[1])
                    if voice_idx < len(self.voice_note_labels):
                        note_val = int(float(value))
                        self.voice_note_labels[voice_idx].setText(str(note_val) if note_val >= 0 else "-")
            except:
                pass
                
        elif var_path.startswith("voice/") and var_path.endswith("/is_active"):
            try:
                parts = var_path.split('/')
                if len(parts) >= 3:
                    voice_idx = int(parts[1])
                    if voice_idx < len(self.voice_active_labels):
                        is_active = float(value) > 0.5
                        self.voice_active_labels[voice_idx].setText("Yes" if is_active else "No")
            except:
                pass
    
    def refresh_ui(self):
        """Refresh UI with current router state"""
        # Request router state
        osc.send_message("/router/get", "voice_manager/active_notes")
        osc.send_message("/router/get", "voice_manager/sustained_notes")
        osc.send_message("/router/get", "router/voices")
        
        # Request voice status for each voice
        voice_count = 4  # Assume at least 4 voices
        for i in range(voice_count):
            osc.send_message("/router/get", f"voice/{i}/note")
            osc.send_message("/router/get", f"voice/{i}/is_active")

# Add new OSC handler for the router
def handle_param_to_all_voices(self, address, *args):
    """Handle sending a parameter to all voices"""
    if len(args) < 1:
        return
    
    param_name = address.split('/')[-1]
    value = float(args[0])
    
    # Get all active voices
    osc.send_message("/router/get", "voice_manager/active_notes")
    # The response will come back with active notes, but we need to send immediately
    
    # For now, send to first 8 voices (safe assumption)
    for i in range(8):
        osc.send_message(f"/router/voice/{i}/param", param_name)
        osc.send_message(f"/router/voice/{i}/param_value", value)

# --- Launch ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    panel = SynthControlPanel()
    panel.resize(600, 800)
    panel.show()
    sys.exit(app.exec())


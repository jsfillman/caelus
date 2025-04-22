import sys
import time
import mido
import threading
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QFrame
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPalette
from pythonosc import udp_client

# --- OSC Setup ---
OSC_IP = "0.0.0.0"  # Listen on all interfaces
OSC_PORT = 9000
ROUTER_NAME = "router"
osc = udp_client.SimpleUDPClient(OSC_IP, OSC_PORT)

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

    def run(self):
        with mido.open_input(self.port_name) as inport:
            while self.running:
                for msg in inport.iter_pending():
                    self.midi_callback(msg)
                time.sleep(0.01)

    def stop(self):
        self.running = False

# --- Main GUI ---
class MidiOscGui(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Caelux MIDI↔OSC Bridge")
        self.setStyleSheet("""
            QWidget { background-color: #111; color: #FFA500; font-family: 'SF Mono', 'Menlo', 'Monaco', monospace; }
            QComboBox, QPushButton { background-color: #222; border: 1px solid #FFA500; padding: 6px; }
            QLabel { font-size: 16px; }
        """)

        layout = QVBoxLayout()

        # --- MIDI Dropdown ---
        self.midi_dropdown = QComboBox()
        self.refresh_midi_ports()
        self.midi_dropdown.currentIndexChanged.connect(self.midi_port_changed)
        layout.addWidget(QLabel("MIDI Input Port:"))
        layout.addWidget(self.midi_dropdown)

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
        for name in ["Load Bank", "Load Patch", "Save Patch"]:
            button = QPushButton(name)
            button.setEnabled(False)  # Dummy for now
            button_row.addWidget(button)
        layout.addLayout(button_row)

        self.setLayout(layout)
        self.worker = None

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
        ports = mido.get_input_names()
        self.midi_dropdown.addItems(ports)

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
        port_name = self.midi_dropdown.currentText()
        self.worker = MidiWorker(port_name, self.handle_midi)
        self.worker.start()

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
        osc.send_message(address, val)
        self.osc_recent = True

    def dim_lights(self):
        set_light(self.midi_light, self.midi_recent)
        set_light(self.osc_light, self.osc_recent)
        self.midi_recent = False
        self.osc_recent = False

    def closeEvent(self, event):
        if self.worker:
            self.worker.stop()
        event.accept()

# --- Launch ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MidiOscGui()
    window.resize(400, 200)
    window.show()
    sys.exit(app.exec())

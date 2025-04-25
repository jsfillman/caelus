import sys
import json
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDial
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from pythonosc import udp_client

# --- Load JSON UI Definition ---
with open("simple.dsp.json") as f:
    synth_ui = json.load(f)

# --- OSC Setup ---
OSC_IP = "127.0.0.1"
OSC_PORT = 9000
ROUTER_NAME = "router"
osc = udp_client.SimpleUDPClient(OSC_IP, OSC_PORT)

# --- Main Synth UI ---
class SynthControlPanel(QWidget):
    def __init__(self, ui_data):
        super().__init__()
        self.setWindowTitle("Caelux Control UI")
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
        """)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        for group in ui_data.get("ui", []):
            for item in group.get("items", []):
                ctrl_type = item["type"]
                label = item.get("label")
                address = item.get("meta", [{}])[0].get("osc", item.get("address"))

                # Skip gate and freq controls
                if label in ["gate", "freq"]:
                    continue

                if ctrl_type == "hslider":
                    self.add_dial(label, address, item["init"], item["min"], item["max"])
                elif ctrl_type == "button":
                    self.add_button(label, address)

    def add_dial(self, name, address, init, min_val, max_val):
        container = QVBoxLayout()
        label = QLabel(name)
        label.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        dial = QDial()
        dial.setMinimum(0)
        dial.setMaximum(1000)
        dial.setValue(int((init - min_val) / (max_val - min_val) * 1000))
        dial.valueChanged.connect(
            lambda val, a=address, minv=min_val, maxv=max_val: self.send_osc(a, minv + (val / 1000) * (maxv - minv))
        )

        container.addWidget(label)
        container.addWidget(dial, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.layout.addLayout(container)

    def add_button(self, name, address):
        button = QPushButton(name)
        button.setCheckable(True)
        button.clicked.connect(lambda checked, a=address: self.send_osc(a, 1.0 if checked else 0.0))
        self.layout.addWidget(button)

    def send_osc(self, address, value):
        full_address = address  # Send clean address directly
        osc.send_message(full_address, float(value))

# --- Launch ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    panel = SynthControlPanel(synth_ui)
    panel.resize(400, 400)
    panel.show()
    sys.exit(app.exec())


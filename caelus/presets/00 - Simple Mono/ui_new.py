
import sys
import json
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QGroupBox, QLineEdit
)
from PyQt6.QtCore import Qt, QTimer, QPointF, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QFont, QColor, QRadialGradient
from PyQt6.QtWidgets import QDial
from pythonosc import udp_client
import math


class NeonDial(QDial):
    value_changed_signal = pyqtSignal(float)

    def __init__(self, min_val, max_val, init_val, scale=1.0, parent=None):
        super().__init__(parent)
        self.setMinimum(0)
        self.setMaximum(1000)
        self.setValue(int((init_val - min_val) / (max_val - min_val) * 1000))
        self.min_val = min_val
        self.max_val = max_val
        self.init_val = init_val
        self.scale = scale
        self.glow_strength = 0
        self.focus = False
        self.setMouseTracking(True)
        self.setNotchesVisible(False)
        self.last_y = None
        self.editing = False
        self.text_box = None

        self.timer = QTimer()
        self.timer.timeout.connect(self.animate_glow)
        self.timer.start(30)

    def animate_glow(self):
        self.glow_strength = (self.glow_strength + 1) % 100
        self.update()

    def enterEvent(self, event):
        self.focus = True
        self.update()

    def leaveEvent(self, event):
        self.focus = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.last_y = event.position().y()

    def mouseDoubleClickEvent(self, event):
        center = QPointF(self.width() / 2, self.height() / 2)
        distance = math.hypot(event.position().x() - center.x(), event.position().y() - center.y())
        radius = min(self.width(), self.height()) // 2 - 6

        if distance <= radius:
            # Inside knob: reset to default
            self.setValue(int((self.init_val - self.min_val) / (self.max_val - self.min_val) * 1000))
        else:
            # Outside: enable text edit
            if not self.editing:
                self.editing = True
                self.text_box = QLineEdit(self.parent())
                self.text_box.setGeometry(self.geometry())
                self.text_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.text_box.setText(f"{self.get_actual_value():.2f}")
                self.text_box.returnPressed.connect(self.finish_editing)
                self.text_box.show()
                self.text_box.setFocus()

    def finish_editing(self):
        try:
            new_val = float(self.text_box.text())
            scaled = (new_val - self.min_val) / (self.max_val - self.min_val) * 1000
            self.setValue(int(max(0, min(1000, scaled))))
        except ValueError:
            pass
        self.text_box.deleteLater()
        self.text_box = None
        self.editing = False

    def mouseMoveEvent(self, event):
        if self.last_y is not None:
            delta = self.last_y - event.position().y()
            new_val = self.value() + delta * 2
            new_val = max(0, min(1000, new_val))
            self.setValue(int(new_val))
            self.last_y = event.position().y()

    def mouseReleaseEvent(self, event):
        self.last_y = None

    def get_actual_value(self):
        return self.min_val + (self.value() / 1000) * (self.max_val - self.min_val)

    def paintEvent(self, event):
        if self.editing:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        radius = min(self.width(), self.height()) // 2 - 6
        center = QPointF(self.width() / 2, self.height() / 2)

        base_alpha = 180 if self.focus else 130
        dynamic_alpha = base_alpha + int(50 * (1 + (self.glow_strength / 100.0)))
        glow_color = QColor(255, 102, 0, min(dynamic_alpha, 255))
        gradient = QRadialGradient(center, radius + 8)
        gradient.setColorAt(0.0, glow_color)
        gradient.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(gradient)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, radius + 8, radius + 8)

        painter.setPen(QPen(QColor("#FF6600"), 3))
        painter.setBrush(QColor(30, 30, 30))
        painter.drawEllipse(center, radius, radius)

        num_leds = 40
        angle_per = 270 / num_leds
        arc_start = 135
        arc_span = int((self.value() / 1000) * 270)

        for i in range(num_leds):
            angle = arc_start + i * angle_per
            rad = math.radians(angle)
            x = center.x() + (radius + 4) * math.cos(rad)
            y = center.y() + (radius + 4) * math.sin(rad)
            color = QColor("#FF6600") if i * angle_per <= arc_span else QColor(80, 40, 20)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(QPointF(x, y), 2.2, 2.2)

        value = self.get_actual_value()
        painter.setPen(QColor("#FFA500"))
        painter.setFont(QFont("SF Mono", 10, QFont.Weight.Bold))
        text = f"{value:.2f}"
        text_rect = painter.boundingRect(self.rect(), Qt.AlignmentFlag.AlignCenter, text)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, text)


# --- OSC Setup ---
OSC_IP = "127.0.0.1"
OSC_PORT = 9000
osc = udp_client.SimpleUDPClient(OSC_IP, OSC_PORT)


class SynthControlPanel(QWidget):
    def __init__(self, ui_data):
        super().__init__()
        self.setWindowTitle("Caelux Micro — Ducking Howard Edition 🦆")
        self.setStyleSheet("""
            QWidget {
                background-color: #111;
                color: #FF6600;
                font-family: 'SF Mono', 'Menlo', monospace;
            }
            QLabel {
                font-size: 13px;
                color: #FF6600;
                padding-bottom: 4px;
            }
            QPushButton {
                background-color: #222;
                color: #FF6600;
                border: 1px solid #FF6600;
                padding: 6px;
                font-weight: bold;
                margin: 4px;
            }
        """)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        for group in ui_data.get("ui", []):
            section = QGroupBox(group.get("label", "Parameters"))
            section.setStyleSheet("QGroupBox { border: 1px solid #FF6600; margin-top: 10px; }")
            section_layout = QVBoxLayout()
            section.setLayout(section_layout)

            for item in group.get("items", []):
                ctrl_type = item["type"]
                label = item.get("label")
                address = item.get("meta", [{}])[0].get("osc", item.get("address"))

                if label in ["gate", "freq"]:
                    continue

                if ctrl_type == "hslider":
                    section_layout.addLayout(
                        self.add_dial(label, address, item["init"], item["min"], item["max"])
                    )
                elif ctrl_type == "button":
                    section_layout.addWidget(self.add_button(label, address))

            self.layout.addWidget(section)

    def add_dial(self, name, address, init, min_val, max_val):
        from PyQt6.QtWidgets import QVBoxLayout
        layout = QVBoxLayout()
        knob = NeonDial(min_val, max_val, init)
        knob.valueChanged.connect(
            lambda val, a=address, minv=min_val, maxv=max_val: self.send_osc(
                a, minv + (val / 1000) * (maxv - minv)
            )
        )
        label = QLabel(name)
        label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(knob, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(label)
        return layout

    def add_button(self, name, address):
        button = QPushButton(name)
        button.setCheckable(True)
        button.clicked.connect(lambda checked, a=address: self.send_osc(a, 1.0 if checked else 0.0))
        return button

    def send_osc(self, address, value):
        osc.send_message(address, float(value))


if __name__ == "__main__":
    with open("synth.dsp.json") as f:
        synth_ui = json.load(f)

    app = QApplication(sys.argv)
    panel = SynthControlPanel(synth_ui)
    panel.resize(500, 600)
    panel.show()
    sys.exit(app.exec())

import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout,
    QHBoxLayout, QGroupBox, QTabWidget, QDial,
    QComboBox, QPushButton, QFileDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

class LabeledKnob(QWidget):
    def __init__(self, label, min_val, max_val, init_val, target, scale=1.0, knob_size=60):
        super().__init__()
        layout = QVBoxLayout()
        layout.setSpacing(2)
        self.dial = QDial()
        self.dial.setMinimum(int(min_val * 100))
        self.dial.setMaximum(int(max_val * 100))
        self.dial.setValue(int(init_val * 100))
        self.dial.setFixedSize(knob_size, knob_size)
        self.dial.setStyleSheet("""
            QDial {
                background: transparent;
            }
        """)
        self.label = QLabel(label)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.dial)
        layout.addWidget(self.label)
        self.setLayout(layout)

class OscillatorPanel(QGroupBox):
    def __init__(self, title):
        super().__init__(title)
        self.setStyleSheet("""
            QGroupBox {
                border: 1px solid #ff6600;
                border-radius: 10px;
                margin-top: 6px;
            }
            QGroupBox:title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 3px;
                color: #ff6600;
            }
        """)
        layout = QHBoxLayout()
        layout.addWidget(LabeledKnob("Freq", 20, 20000, 440, "freq"))
        layout.addWidget(LabeledKnob("Gain", 0, 1, 0.5, "gain"))
        layout.addWidget(LabeledKnob("Pan", 0, 1, 0.5, "pan"))
        self.setLayout(layout)

class CaeluxUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Caelux Micro: Ducking Howard Edition")
        self.setStyleSheet("""
            QWidget {
                background-color: #0d0d0d;
                color: #ff6600;
                font-family: 'Orbitron', 'Arial';
                font-size: 14px;
                letter-spacing: 1px;
            }
            QPushButton {
                border: 1px solid #ff6600;
                border-radius: 4px;
                padding: 5px;
                color: #ff6600;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: rgba(255, 102, 0, 0.2);
            }
            QLabel {
                color: #ff6600;
                font-weight: bold;
            }
        """)
        layout = QVBoxLayout()

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("QTabBar::tab { color: #ff6600; padding: 6px; } QTabWidget::pane { border: 1px solid #ff6600; }")

        for i in range(1, 4):
            osc_panel = OscillatorPanel(f"Oscillator {i}")
            tab = QWidget()
            tab_layout = QVBoxLayout()
            tab_layout.addWidget(osc_panel)
            tab.setLayout(tab_layout)
            self.tabs.addTab(tab, f"OSC {i}")

        layout.addWidget(self.tabs)
        self.setLayout(layout)

def main():
    app = QApplication(sys.argv)
    ui = CaeluxUI()
    ui.resize(600, 400)
    ui.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()


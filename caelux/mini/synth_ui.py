from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QDoubleSpinBox,
    QGroupBox, QApplication, QComboBox
)
from PyQt5.QtCore import Qt

class SynthUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Caelux Control UI")

        layout = QVBoxLayout()
        layout.addWidget(self._make_freq_panel())
        layout.addWidget(self._make_amp_panel())
        self.setLayout(layout)

    def _make_slider(self, label, min_val, max_val, default, step=None):
        layout = QHBoxLayout()
        lbl = QLabel(label)
        spin = QDoubleSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(default)
        spin.setSingleStep(step if step else (max_val - min_val) / 100.0)
        spin.setDecimals(3)
        layout.addWidget(lbl)
        layout.addWidget(spin)
        return layout

    def _make_freq_panel(self):
        box = QGroupBox("Frequency Controls")
        vbox = QVBoxLayout()

        # Frequency mode selection
        mode_layout = QHBoxLayout()
        mode_label = QLabel("Frequency Mode:")
        self.freq_mode = QComboBox()
        self.freq_mode.addItems(["MIDI Note", "Manual"])
        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.freq_mode)
        vbox.addLayout(mode_layout)

        # Manual frequency input
        self.manual_freq = self._make_slider("Manual Frequency (Hz)", 0.01, 20000.0, 440.0)
        vbox.addLayout(self.manual_freq)

        # Enable/disable manual freq input based on mode
        def toggle_manual_freq(index):
            self.manual_freq.itemAt(1).widget().setEnabled(index == 1)

        self.freq_mode.currentIndexChanged.connect(toggle_manual_freq)
        toggle_manual_freq(self.freq_mode.currentIndex())  # Initialize state

        # Freq sweep & env
        self.start_rand = self._make_slider("Start Rand (Hz)", 0, 100, 0)
        self.start_slew = self._make_slider("Start Slew (Hz)", -1000, 1000, 0)
        self.end_slew = self._make_slider("End Slew (Hz)", -1000, 1000, 0)
        self.slew_time = self._make_slider("Slew Time (sec)", 0.01, 600, 0.01)


        self.freq_attack = self._make_slider("Freq Attack", 0.001, 10, 0.0)
        self.freq_decay = self._make_slider("Freq Decay", 0.001, 10, 0.0)
        self.freq_sustain = self._make_slider("Freq Sustain", 0, 1, 0.0)
        self.freq_release = self._make_slider("Freq Release", 0.001, 10, 0.0)
        self.freq_env_depth = self._make_slider("Freq Env Depth", 0, 2000, 0)


        for widget in [
            self.start_rand, self.start_slew, self.end_slew, self.slew_time,
            self.freq_attack, self.freq_decay, self.freq_sustain, self.freq_release
        ]:
            vbox.addLayout(widget)
        vbox.addLayout(self.freq_env_depth)

        box.setLayout(vbox)
        return box

    def _make_amp_panel(self):
        box = QGroupBox("Amplitude Controls")
        vbox = QVBoxLayout()

        self.amp_ramp_start = self._make_slider("Amp Ramp Start", 0.0, 1.0, 0.0)
        self.amp_ramp_end = self._make_slider("Amp Ramp End", 0.0, 1.0, 1.0)
        self.amp_ramp_time = self._make_slider("Amp Ramp Time (sec)", 0.001, 10, 1.0)

        self.amp_attack = self._make_slider("Amp Attack", 0.001, 10, 0.01)
        self.amp_decay = self._make_slider("Amp Decay", 0.001, 10, 0.1)
        self.amp_sustain = self._make_slider("Amp Sustain", 0, 1, 0.7)
        self.amp_release = self._make_slider("Amp Release", 0.001, 10, 0.5)

        for widget in [
            self.amp_ramp_start, self.amp_ramp_end, self.amp_ramp_time,
            self.amp_attack, self.amp_decay, self.amp_sustain, self.amp_release
        ]:
            vbox.addLayout(widget)

        box.setLayout(vbox)
        return box

# Run standalone for testing
if __name__ == "__main__":
    app = QApplication([])
    win = SynthUI()
    win.show()
    app.exec_()


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
        layout.addWidget(self._make_delay_panel())
        layout.addWidget(self._make_feedback_panel())
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

        mode_layout = QHBoxLayout()
        mode_label = QLabel("Frequency Mode:")
        self.freq_mode = QComboBox()
        self.freq_mode.addItems(["MIDI Note", "Manual"])
        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.freq_mode)
        vbox.addLayout(mode_layout)

        self.manual_freq = self._make_slider("Manual Frequency (Hz)", 0.01, 20000.0, 440.0)
        vbox.addLayout(self.manual_freq)

        def toggle_manual_freq(index):
            self.manual_freq.itemAt(1).widget().setEnabled(index == 1)

        self.freq_mode.currentIndexChanged.connect(toggle_manual_freq)
        toggle_manual_freq(self.freq_mode.currentIndex())

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
            self.freq_attack, self.freq_decay, self.freq_sustain, self.freq_release,
            self.freq_env_depth
        ]:
            vbox.addLayout(widget)

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

    def _make_delay_panel(self):
        box = QGroupBox("Delay Controls (Stereo Multitap)")
        vbox = QVBoxLayout()

        self.left_delays = [
            self._make_slider("Left Tap 1 (s)", 0.01, 2.0, 0.15),
            self._make_slider("Left Tap 2 (s)", 0.01, 2.0, 0.35),
            self._make_slider("Left Tap 3 (s)", 0.01, 2.0, 0.55)
        ]
        self.right_delays = [
            self._make_slider("Right Tap 1 (s)", 0.01, 2.0, 0.2),
            self._make_slider("Right Tap 2 (s)", 0.01, 2.0, 0.4),
            self._make_slider("Right Tap 3 (s)", 0.01, 2.0, 0.6)
        ]
        self.left_feedback = self._make_slider("Left Feedback", 0.0, 0.99, 0.3)
        self.right_feedback = self._make_slider("Right Feedback", 0.0, 0.99, 0.3)

        for tap in self.left_delays + self.right_delays:
            vbox.addLayout(tap)
        vbox.addLayout(self.left_feedback)
        vbox.addLayout(self.right_feedback)

        box.setLayout(vbox)
        return box

    def _make_feedback_panel(self):
        box = QGroupBox("Feedback")
        vbox = QVBoxLayout()

        fb_layout = QHBoxLayout()
        fb_label = QLabel("Feedback Source:")
        self.feedback_source = QComboBox()
        self.feedback_source.addItems(["Off", "Pre-Delay", "Post-Delay"])
        fb_layout.addWidget(fb_label)
        fb_layout.addWidget(self.feedback_source)
        vbox.addLayout(fb_layout)

        self.feedback_depth = self._make_slider("Feedback Depth", 0.0, 1000.0, 0.0)

        vbox.addLayout(self.feedback_depth)

        box.setLayout(vbox)
        return box

if __name__ == "__main__":
    app = QApplication([])
    win = SynthUI()
    win.show()
    app.exec_()

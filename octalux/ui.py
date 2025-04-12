import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout,
    QHBoxLayout, QGroupBox, QTabWidget, QDial, QComboBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

class LabeledKnob(QWidget):
    def __init__(self, label, min_val, max_val, init_val, target, scale=1.0, knob_size=60):
        super().__init__()
        layout = QHBoxLayout()
        layout.setSpacing(10)

        self.dial = QDial()
        self.dial.setMinimum(int(min_val * 100))
        self.dial.setMaximum(int(max_val * 100))
        self.dial.setValue(int(init_val * 100))
        self.dial.setFixedSize(knob_size, knob_size)
        self.dial.valueChanged.connect(lambda val: self.update_value(val / 100.0, target, label))

        self.label = QLabel(f"{label}: {init_val:.2f}")
        self.label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.label.setFont(QFont("Arial", 10))

        layout.addWidget(self.dial)
        layout.addWidget(self.label)
        layout.setContentsMargins(5, 5, 5, 5)

        self.setLayout(layout)

    def update_value(self, val, target, label):
        self.label.setText(f"{label}: {val:.2f}")
        if callable(target):
            target(val)
        else:
            target.setValue(val)


class SynthControlUI(QWidget):
    def __init__(self, vol_control, oscillators, waveform_bank):
        super().__init__()
        self.setWindowTitle("Synth Controls")
        self.setFixedSize(720, 480)

        tabs = QTabWidget()

        # === GLOBAL TAB ===
        global_tab = QWidget()
        global_layout = QVBoxLayout()
        global_knob = LabeledKnob("Volume", 0, 11, int(vol_control.value), vol_control, scale=1.0, knob_size=100)
        global_layout.addStretch()
        global_layout.addWidget(global_knob, alignment=Qt.AlignmentFlag.AlignHCenter)
        global_layout.addStretch()
        global_tab.setLayout(global_layout)
        tabs.addTab(global_tab, "G")

        # === OSCILLATOR TABS ===
        for i, osc in enumerate(oscillators):
            semi, cents, osc_obj, cutoff, lfo_rate, lfo_depth, res = osc.get_ui_controls()
        
            tab = QWidget()
            layout = QVBoxLayout()
        
            # === Waveform dropdown ===
            dropdown = QComboBox()
            dropdown.addItems(waveform_bank.get_table_list())
            dropdown.setCurrentText(osc.table_name)
            dropdown.currentTextChanged.connect(osc.set_waveform)
            layout.addWidget(dropdown)
        
            # === Horizontal row containing 3 columns ===
            row = QHBoxLayout()
        
            # === Detune column ===
            detune_col = QVBoxLayout()
            detune_col.addWidget(LabeledKnob(f"Semi {i+1}", -12, 12, int(semi.value), semi, knob_size=60))
            detune_col.addWidget(LabeledKnob(f"Cents {i+1}", -100, 100, int(cents.value), cents, knob_size=60))
            row.addLayout(detune_col)
        
            # === ADSR column ===
            adsr_col = QVBoxLayout()
            adsr_col.addWidget(LabeledKnob(f"Attack {i+1}", 0.01, 2.0, osc_obj.attack_val, osc_obj.set_attack, knob_size=60))
            adsr_col.addWidget(LabeledKnob(f"Decay {i+1}", 0.01, 2.0, osc_obj.decay_val, osc_obj.set_decay, knob_size=60))
            adsr_col.addWidget(LabeledKnob(f"Sustain {i+1}", 0.0, 1.0, osc_obj.sustain_val, osc_obj.set_sustain, knob_size=60))
            adsr_col.addWidget(LabeledKnob(f"Release {i+1}", 0.01, 2.0, osc_obj.release_val, osc_obj.set_release, knob_size=60))
            row.addLayout(adsr_col)
        
            # === LPF / LFO column ===
            filter_col = QVBoxLayout()
            filter_col.addWidget(LabeledKnob(f"Cutoff {i+1}", 100, 5000, cutoff.value, cutoff, knob_size=60))
            filter_col.addWidget(LabeledKnob(f"LFO Rate {i+1}", 0.01, 10.0, lfo_rate.value, lfo_rate, knob_size=60))
            filter_col.addWidget(LabeledKnob(f"LFO Depth {i+1}", 0.0, 2000, lfo_depth.value, lfo_depth, knob_size=60))
            filter_col.addWidget(LabeledKnob(f"Resonance {i+1}", 0.0, 1.0, res.value, res, knob_size=60))
            row.addLayout(filter_col)
        
            layout.addLayout(row)
            tab.setLayout(layout)
            tabs.addTab(tab, f"O{i+1}")
        

        

        layout = QVBoxLayout()
        layout.addWidget(tabs)
        self.setLayout(layout)

def get_ui_controls(self):
    return self.semi, self.cents, self  # so the UI can call osc.set_attack()


def run_ui(vol_control, oscillators, waveform_bank):
    app = QApplication(sys.argv)
    window = SynthControlUI(vol_control, oscillators, waveform_bank)
    window.show()
    sys.exit(app.exec())

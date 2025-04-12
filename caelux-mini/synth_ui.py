from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QDoubleSpinBox,
    QGroupBox, QApplication, QComboBox, QScrollArea
)
from PyQt5.QtCore import Qt
from wavetables import WaveformBank

class SynthUI(QWidget):
    def __init__(self, server=None):  # Add server parameter with default None
        super().__init__()
        
        # Store the server reference
        self.server = server
        
        # Initialize the wavetable manager 
        self.wave_bank = WaveformBank()
        
        # If server is running, create the tables
        if server:
            self.wave_bank.create_standard_tables()
            self.wave_types = self.wave_bank.get_table_list()
        else:
            # Fallback list of expected table names if server isn't running yet
            self.wave_types = ["sine", "saw", "square", "triangle", "octaves", 
                              "evens", "odds", "organ", "formant1", "formant2", 
                              "brass", "cheby1", "cheby2", "plucked", "clarinet"]
        
        # Create a scroll area to contain all controls
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        # Create a container widget for the scroll area
        scroll_widget = QWidget()
        
        # Create a horizontal layout for panels
        main_layout = QHBoxLayout(scroll_widget)
        main_layout.setSpacing(20)

        # Add panels in signal flow order
        main_layout.addWidget(self.make_oscillator_panel())
        main_layout.addWidget(self._make_freq_panel())
        main_layout.addWidget(self._make_amp_panel())
        
        # Create a panel for filter and feedback
        filter_feedback_panel = QWidget()
        filter_layout = QVBoxLayout(filter_feedback_panel)
        filter_layout.addWidget(self._make_filter_panel())
        filter_layout.addWidget(self._make_feedback_panel())
        
        main_layout.addWidget(filter_feedback_panel)
        main_layout.addWidget(self._make_delay_panel())
        
        # Set up the scroll area with our content
        scroll_area.setWidget(scroll_widget)
        
        # Create a layout for the tab content
        tab_layout = QVBoxLayout(self)
        tab_layout.addWidget(QLabel("Carrier 1 Controls"))
        tab_layout.addWidget(scroll_area)
        
        # Set minimum width for consistent appearance
        self.setMinimumWidth(1450)
    
    def make_oscillator_panel(self):
        """Create controls for oscillator bank parameters"""
        box = QGroupBox("Oscillator")
        vbox = QVBoxLayout()
        
        # Waveform selection
        wave_layout = QHBoxLayout()
        wave_label = QLabel("Waveform:")
        self.wave_type = QComboBox()
        self.wave_type.addItems(self.wave_types)
        wave_layout.addWidget(wave_label)
        wave_layout.addWidget(self.wave_type)
        vbox.addLayout(wave_layout)
        
        # Number of oscillators
        self.num_oscs = self._make_slider("Number of Oscillators", 2, 20, 8, 2)
        vbox.addLayout(self.num_oscs)
        
        # Detune amount
        self.detune = self._make_slider("Detune", 0.0, 0.1, 0.001, 0.001)
        vbox.addLayout(self.detune)
        
        # Spread factor
        self.spread = self._make_slider("Spread", 0.0, 1.0, 0.005, 0.001)
        vbox.addLayout(self.spread)
        
        # Detune mode (could be linear, exponential, etc.)
        det_mode_layout = QHBoxLayout()
        det_mode_label = QLabel("Detune Mode:")
        self.detune_mode = QComboBox()
        self.detune_mode.addItems(["Linear", "Exponential", "Random"])
        det_mode_layout.addWidget(det_mode_label)
        det_mode_layout.addWidget(self.detune_mode)
        vbox.addLayout(det_mode_layout)
        
        # Phase spread
        self.phase_spread = self._make_slider("Phase Spread", 0.0, 1.0, 0.0, 0.01)
        vbox.addLayout(self.phase_spread)
        
        # Amplitude distribution
        amp_dist_layout = QHBoxLayout()
        amp_dist_label = QLabel("Amplitude:")
        self.amp_dist = QComboBox()
        self.amp_dist.addItems(["Equal", "Decreasing", "Increasing", "Triangle", "Bell"])
        amp_dist_layout.addWidget(amp_dist_label)
        amp_dist_layout.addWidget(self.amp_dist)
        vbox.addLayout(amp_dist_layout)
        
        box.setLayout(vbox)
        return box

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

        # Mode selection
        mode_layout = QHBoxLayout()
        mode_label = QLabel("Frequency Mode:")
        self.freq_mode = QComboBox()
        self.freq_mode.addItems(["MIDI Note", "Manual"])
        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.freq_mode)
        vbox.addLayout(mode_layout)

        # Create the manual frequency control
        self.manual_freq = self._make_slider("Manual Frequency (Hz)", 0.01, 20000.0, 440.0)
        vbox.addLayout(self.manual_freq)

        # Create coarse and fine detune controls
        self.coarse_detune = self._make_slider("Coarse Detune (semitones)", -24, 24, 0, 1)
        self.fine_detune = self._make_slider("Fine Detune (cents)", -100, 100, 0, 1)
        vbox.addLayout(self.coarse_detune)
        vbox.addLayout(self.fine_detune)

        # Create the slew/ramp controls - in consistent order
        self.slew_delay = self._make_slider("Slew Delay (sec)", 0.0, 10.0, 0.0)
        self.slew_time = self._make_slider("Slew Time (sec)", 0.01, 600, 0.01)
        self.start_rand = self._make_slider("Start Rand (Hz)", 0, 100, 0)
        self.start_slew = self._make_slider("Start Slew (Hz)", -1000, 1000, 0)
        self.end_slew = self._make_slider("End Slew (Hz)", -1000, 1000, 0)
        
        # Place frequency envelope depth before ADSR
        self.freq_env_depth = self._make_slider("Freq Env Depth", 0, 2000, 0)
        
        # Create frequency envelope controls
        self.freq_attack = self._make_slider("Freq Attack", 0.001, 10, 0.0)
        self.freq_decay = self._make_slider("Freq Decay", 0.001, 10, 0.0)
        self.freq_sustain = self._make_slider("Freq Sustain", 0, 1, 0.0)
        self.freq_release = self._make_slider("Freq Release", 0.001, 10, 0.0)

        # Add all controls to the panel in the proper order
        vbox.addLayout(self.slew_delay)
        vbox.addLayout(self.slew_time)
        vbox.addLayout(self.start_rand)
        vbox.addLayout(self.start_slew)
        vbox.addLayout(self.end_slew)
        vbox.addLayout(self.freq_env_depth)
        vbox.addLayout(self.freq_attack)
        vbox.addLayout(self.freq_decay)
        vbox.addLayout(self.freq_sustain)
        vbox.addLayout(self.freq_release)

        box.setLayout(vbox)
        return box

    def _make_amp_panel(self):
        box = QGroupBox("Amplitude Controls")
        vbox = QVBoxLayout()

        # Create amplitude ramp controls - in consistent order
        self.amp_ramp_delay = self._make_slider("Amp Ramp Delay (sec)", 0.0, 10.0, 0.0)
        self.amp_ramp_time = self._make_slider("Amp Ramp Time (sec)", 0.001, 10, 1.0)
        self.amp_ramp_start = self._make_slider("Amp Ramp Start", 0.0, 1.0, 0.0)
        self.amp_ramp_end = self._make_slider("Amp Ramp End", 0.0, 1.0, 1.0)

        # Create ADSR envelope controls
        self.amp_attack = self._make_slider("Amp Attack", 0.001, 10, 0.01)
        self.amp_decay = self._make_slider("Amp Decay", 0.001, 10, 0.1)
        self.amp_sustain = self._make_slider("Amp Sustain", 0, 1, 0.7)
        self.amp_release = self._make_slider("Amp Release", 0.001, 10, 0.5)

        # Add controls to the panel in proper order
        vbox.addLayout(self.amp_ramp_delay)
        vbox.addLayout(self.amp_ramp_time)
        vbox.addLayout(self.amp_ramp_start)
        vbox.addLayout(self.amp_ramp_end)
        vbox.addLayout(self.amp_attack)
        vbox.addLayout(self.amp_decay)
        vbox.addLayout(self.amp_sustain)
        vbox.addLayout(self.amp_release)

        box.setLayout(vbox)
        return box

    def _make_filter_panel(self):
        box = QGroupBox("LPF")
        vbox = QVBoxLayout()
    
        # Resonance control
        self.filter_res = self._make_slider("Filter Resonance", 0.0, 0.99, 0.3)
        
        # Create filter ramp controls
        self.filter_ramp_delay = self._make_slider("Filter Ramp Delay (sec)", 0.0, 10.0, 0.0)
        self.filter_ramp_time = self._make_slider("Filter Ramp Time (sec)", 0.001, 10.0, 1.0)
        self.filter_ramp_start = self._make_slider("Filter Ramp Start (Hz)", 20.0, 20000.0, 100.0)
        self.filter_ramp_end = self._make_slider("Filter Ramp End (Hz)", 20.0, 20000.0, 5000.0)
    
        # Add all controls to the panel
        vbox.addLayout(self.filter_res)
        vbox.addLayout(self.filter_ramp_delay)
        vbox.addLayout(self.filter_ramp_time)
        vbox.addLayout(self.filter_ramp_start)
        vbox.addLayout(self.filter_ramp_end)
    
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

    def _make_delay_panel(self):
        box = QGroupBox("Delay Controls")
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

if __name__ == "__main__":
    app = QApplication([])
    win = SynthUI()
    win.show()
    app.exec_()

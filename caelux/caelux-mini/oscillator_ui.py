from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QDoubleSpinBox,
    QGroupBox, QApplication, QComboBox, QScrollArea, QCheckBox,
    QGridLayout
)
from PyQt5.QtCore import Qt, pyqtSignal
from wavetables import WaveformBank

class OscillatorUI(QWidget):
    # Define signals for bypass toggles
    osc_bypass_toggled = pyqtSignal(bool)
    freq_bypass_toggled = pyqtSignal(bool)
    amp_bypass_toggled = pyqtSignal(bool)
    filter_bypass_toggled = pyqtSignal(bool)
    delay_bypass_toggled = pyqtSignal(bool)
    
    # Define signals for panner controls
    pan_position_changed_signal = pyqtSignal(float)
    stereo_width_changed_signal = pyqtSignal(float)
    autopan_toggled_signal = pyqtSignal(bool)
    autopan_rate_changed_signal = pyqtSignal(float)
    
    # Define signals for matrix routing
    routing_changed_signal = pyqtSignal(str, str, float)  # source, destination, amount
    channel_routing_changed_signal = pyqtSignal(str, int, float)  # oscillator, channel, amount
    
    def __init__(self, server=None, osc_name="C1", osc_type="carrier"):
        super().__init__()
        
        # Store the server reference
        self.server = server
        self.osc_name = osc_name  # This is the displayed name
        self.name = osc_name      # This is the internal name used for routing
        self.osc_type = osc_type
        
        # Bypass state
        self.bypass_state = {
            'osc': False,
            'freq': False,
            'amp': False,
            'filter': False,
            'delay': False
        }
        
        # Initialize the wavetable manager 
        self.wave_bank = WaveformBank(server)
        
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
        main_layout.addWidget(self._make_panner_panel())
        
        # Set up the scroll area with our content
        scroll_area.setWidget(scroll_widget)
        
        # Create a layout for the tab content
        tab_layout = QVBoxLayout(self)
        tab_layout.addWidget(QLabel(f"{self.osc_type.capitalize()} {self.osc_name[-1]} Controls"))
        tab_layout.addWidget(scroll_area)
        
        # Set minimum width for consistent appearance
        self.setMinimumWidth(1200)
    
    def make_oscillator_panel(self):
        """Create controls for oscillator bank parameters"""
        box = QGroupBox("Oscillator")
        vbox = QVBoxLayout()
        
        # Add bypass checkbox
        bypass_layout = QHBoxLayout()
        self.osc_bypass_checkbox = QCheckBox("Bypass Oscillator")
        self.osc_bypass_checkbox.setChecked(self.bypass_state['osc'])
        self.osc_bypass_checkbox.stateChanged.connect(self._on_osc_bypass_changed)
        bypass_layout.addWidget(self.osc_bypass_checkbox)
        bypass_layout.addStretch()
        vbox.addLayout(bypass_layout)
        
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

        # Add bypass checkbox
        bypass_layout = QHBoxLayout()
        self.freq_bypass_checkbox = QCheckBox("Bypass Frequency Processing")
        self.freq_bypass_checkbox.setChecked(self.bypass_state['freq'])
        self.freq_bypass_checkbox.stateChanged.connect(self._on_freq_bypass_changed)
        bypass_layout.addWidget(self.freq_bypass_checkbox)
        bypass_layout.addStretch()
        vbox.addLayout(bypass_layout)

        # For Carrier, add a dedicated modulation controls section at the top
        if self.osc_type == "carrier":
            mod_group = QGroupBox("Modulation Matrix")
            mod_layout = QVBoxLayout()
            
            # For each possible modulation source, create a slider
            # Currently we support OP1, CAR1, and CAR2 as mod sources
            self.mod_sources = ["OP1", "CAR1", "CAR2"]
            self.mod_amount_sliders = {}
            
            # Add a grid for mod sources
            for source in self.mod_sources:
                # Skip self-modulation for simplicity
                if source == self.name:
                    print(f"Skipping self-modulation for {self.name}")
                    continue
                    
                # Create a slider for this mod source
                self.mod_amount_sliders[source] = self._make_slider(
                    f"Mod from {source}", 0.0, 1000.0, 
                    100.0 if source == "OP1" else 0.0,  # Default to 100 for OP1, 0 for others
                    1.0
                )
                mod_layout.addLayout(self.mod_amount_sliders[source])
                
                # Connect the slider to the signal
                slider = self.mod_amount_sliders[source].itemAt(1).widget()
                # Use a lambda with default argument to avoid closure issues
                slider.valueChanged.connect(
                    lambda value, src=source: self._on_mod_amount_changed(src, value)
                )
            
            # For backward compatibility, set the generic mod_amount to the OP1 amount
            if "OP1" in self.mod_amount_sliders:
                self.mod_amount = self.mod_amount_sliders["OP1"]
            
            mod_group.setLayout(mod_layout)
            vbox.addWidget(mod_group)
            
            # Add a separator
            line = QLabel("")
            line.setFixedHeight(10)
            vbox.addWidget(line)

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
        
    def _on_mod_amount_changed(self, source, value):
        """Handle modulation amount change from a source"""
        # Emit signal with source, destination (self), and amount
        self.routing_changed_signal.emit(source, self.name, value)

    def _make_amp_panel(self):
        box = QGroupBox("Amplitude Controls")
        vbox = QVBoxLayout()

        # Add bypass checkbox
        bypass_layout = QHBoxLayout()
        self.amp_bypass_checkbox = QCheckBox("Bypass Amplitude Processing")
        self.amp_bypass_checkbox.setChecked(self.bypass_state['amp'])
        self.amp_bypass_checkbox.stateChanged.connect(self._on_amp_bypass_changed)
        bypass_layout.addWidget(self.amp_bypass_checkbox)
        bypass_layout.addStretch()
        vbox.addLayout(bypass_layout)

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
        
        # Add bypass checkbox
        bypass_layout = QHBoxLayout()
        self.filter_bypass_checkbox = QCheckBox("Bypass Filter")
        self.filter_bypass_checkbox.setChecked(self.bypass_state['filter'])
        self.filter_bypass_checkbox.stateChanged.connect(self._on_filter_bypass_changed)
        bypass_layout.addWidget(self.filter_bypass_checkbox)
        bypass_layout.addStretch()
        vbox.addLayout(bypass_layout)
    
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
        
        # Add bypass checkbox
        bypass_layout = QHBoxLayout()
        self.delay_bypass_checkbox = QCheckBox("Bypass Delay")
        self.delay_bypass_checkbox.setChecked(self.bypass_state['delay'])
        self.delay_bypass_checkbox.stateChanged.connect(self._on_delay_bypass_changed)
        bypass_layout.addWidget(self.delay_bypass_checkbox)
        bypass_layout.addStretch()
        vbox.addLayout(bypass_layout)

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
        
    def _make_panner_panel(self):
        """Create controls for the stereo panner and routing"""
        box = QGroupBox("Output Routing")
        vbox = QVBoxLayout()
        
        # Only show output routing for carriers
        if self.osc_type == "carrier":
            # Create a routing group
            routing_group = QGroupBox("Channel Routing")
            routing_layout = QVBoxLayout()
            
            # Create sliders for each output channel
            self.channel_sliders = []
            
            # Define the output channels 
            channel_names = ["Front Left", "Front Right", "Rear Left", "Rear Right"]
            
            # Default value for current carrier (1.0 for its default channel, 0 for others)
            def get_default_value(channel):
                if self.name == "CAR1" and channel == 0:  # CAR1 -> Front Left
                    return 1.0
                elif self.name == "CAR2" and channel == 1:  # CAR2 -> Front Right
                    return 1.0
                # Future carriers would go to rear channels
                elif self.name == "CAR3" and channel == 2:  # CAR3 -> Rear Left
                    return 1.0
                elif self.name == "CAR4" and channel == 3:  # CAR4 -> Rear Right
                    return 1.0
                return 0.0
            
            # Create controls for each channel
            for i, name in enumerate(channel_names):
                slider = self._make_slider(f"{name} (Ch {i+1})", 0.0, 1.0, get_default_value(i), 0.01)
                routing_layout.addLayout(slider)
                self.channel_sliders.append(slider)
                
                # Connect the slider to channel routing signal
                channel_slider = slider.itemAt(1).widget()
                # Use lambda with default argument to avoid closure issues
                channel_slider.valueChanged.connect(
                    lambda value, ch=i: self._on_channel_routing_changed(ch, value)
                )
            
            routing_group.setLayout(routing_layout)
            vbox.addWidget(routing_group)
        
        # Pan position slider
        self.pan_position = self._make_slider("Pan Position", 0.0, 1.0, 0.5, 0.01)
        vbox.addLayout(self.pan_position)
        
        # Stereo width slider
        self.stereo_width = self._make_slider("Stereo Width", 0.0, 1.0, 1.0, 0.01)
        vbox.addLayout(self.stereo_width)
        
        # Autopan controls
        autopan_layout = QHBoxLayout()
        self.autopan_checkbox = QCheckBox("Enable Autopan")
        autopan_layout.addWidget(self.autopan_checkbox)
        autopan_layout.addStretch()
        vbox.addLayout(autopan_layout)
        
        # Autopan rate (LFO frequency)
        self.autopan_rate = self._make_slider("Autopan Rate (Hz)", 0.01, 10.0, 0.2, 0.01)
        vbox.addLayout(self.autopan_rate)
        
        # Add signals
        self.pan_position.itemAt(1).widget().valueChanged.connect(self._on_pan_position_changed)
        self.stereo_width.itemAt(1).widget().valueChanged.connect(self._on_stereo_width_changed)
        self.autopan_checkbox.stateChanged.connect(self._on_autopan_toggled)
        self.autopan_rate.itemAt(1).widget().valueChanged.connect(self._on_autopan_rate_changed)
        
        box.setLayout(vbox)
        return box
        
    def _on_channel_routing_changed(self, channel, value):
        """Handle channel routing amount change"""
        # Emit signal with oscillator name, channel, and amount
        self.channel_routing_changed_signal.emit(self.name, channel, value)
    
    # Event handlers for bypass checkboxes
    def _on_osc_bypass_changed(self, state):
        """Handle oscillator bypass checkbox changes"""
        bypass = state == Qt.Checked
        self.bypass_state['osc'] = bypass
        self.osc_bypass_toggled.emit(bypass)
        
    def _on_freq_bypass_changed(self, state):
        """Handle frequency bypass checkbox changes"""
        bypass = state == Qt.Checked
        self.bypass_state['freq'] = bypass
        self.freq_bypass_toggled.emit(bypass)
        
    def _on_amp_bypass_changed(self, state):
        """Handle amplitude bypass checkbox changes"""
        bypass = state == Qt.Checked
        self.bypass_state['amp'] = bypass
        self.amp_bypass_toggled.emit(bypass)
        
    def _on_filter_bypass_changed(self, state):
        """Handle filter bypass checkbox changes"""
        bypass = state == Qt.Checked
        self.bypass_state['filter'] = bypass
        self.filter_bypass_toggled.emit(bypass)
        
    def _on_delay_bypass_changed(self, state):
        """Handle delay bypass checkbox changes"""
        bypass = state == Qt.Checked
        self.bypass_state['delay'] = bypass
        self.delay_bypass_toggled.emit(bypass)
        
    def set_bypass_state(self, section, state):
        """Set the bypass state for a section
        
        Args:
            section (str): The section to modify ('osc', 'freq', 'amp', 'filter', 'delay')
            state (bool): True to bypass, False to enable
        """
        self.bypass_state[section] = state
        
        # Update the corresponding checkbox
        if section == 'osc':
            self.osc_bypass_checkbox.setChecked(state)
        elif section == 'freq':
            self.freq_bypass_checkbox.setChecked(state)
        elif section == 'amp':
            self.amp_bypass_checkbox.setChecked(state)
        elif section == 'filter':
            self.filter_bypass_checkbox.setChecked(state)
        elif section == 'delay':
            self.delay_bypass_checkbox.setChecked(state)
            
    # Event handlers for panner controls
    def _on_pan_position_changed(self, value):
        """Handle pan position changes"""
        self.pan_position_changed_signal.emit(value)
        
    def _on_stereo_width_changed(self, value):
        """Handle stereo width changes"""
        self.stereo_width_changed_signal.emit(value)
        
    def _on_autopan_toggled(self, state):
        """Handle autopan toggle"""
        enabled = state == Qt.Checked
        self.autopan_toggled_signal.emit(enabled)
        
    def _on_autopan_rate_changed(self, value):
        """Handle autopan rate changes"""
        self.autopan_rate_changed_signal.emit(value)
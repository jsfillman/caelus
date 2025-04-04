from pyo import *
import mido
from threading import Thread
from PyQt5.QtWidgets import (QApplication, QMainWindow, QSlider, QVBoxLayout, QHBoxLayout, 
                            QLabel, QWidget, QTabWidget, QGroupBox, QGridLayout, 
                            QRadioButton, QButtonGroup, QDoubleSpinBox, QSpinBox)
from PyQt5.QtCore import Qt, QTimer
import sys
import time


class MidiController:
    """Handles MIDI input/output functionality"""
    
    def __init__(self, synth_engine):
        """Initialize MIDI controller with reference to synth engine"""
        self.synth_engine = synth_engine
        self.current_note = None
        self.midi_thread = None
        self.is_running = False
        self.midi_status = "Not connected"
        self.status_callback = None
    
    def set_status_callback(self, callback):
        """Set callback for status updates"""
        self.status_callback = callback
    
    def start(self):
        """Start MIDI handling in a separate thread"""
        if not self.midi_thread:
            self.is_running = True
            self.midi_thread = Thread(target=self.midi_loop, daemon=True)
            self.midi_thread.start()
    
    def stop(self):
        """Stop MIDI handling"""
        self.is_running = False
        if self.midi_thread:
            self.midi_thread.join(timeout=1.0)
            self.midi_thread = None
    
    def update_status(self, status):
        """Update MIDI status and notify callback"""
        self.midi_status = status
        if self.status_callback:
            self.status_callback(status)
    
    def midi_loop(self):
        """Main MIDI processing loop"""
        try:
            # Find MIDI device
            available_ports = mido.get_input_names()
            if not available_ports:
                self.update_status("No MIDI devices found")
                raise Exception("No MIDI devices found")
            
            port_name = available_ports[0]  # Use first available MIDI input
            self.update_status(f"Connected: {port_name}")
            
            with mido.open_input(port_name) as port:
                while self.is_running:
                    # Non-blocking message check
                    for msg in port.iter_pending():
                        self.process_midi_message(msg)
                    
                    # Sleep to prevent CPU hogging
                    time.sleep(0.001)
                    
        except Exception as e:
            self.update_status(f"Error: {str(e)}")
            print(f"Error with MIDI: {e}")
            print("Playing without MIDI. Use computer keyboard to test:")
            print("Press 'a' to play a note, 's' to stop")
            
            # Set up keyboard handler as fallback
            self.setup_keyboard_fallback()
    
    def process_midi_message(self, msg):
        """Process incoming MIDI messages"""
        print(f"MIDI: {msg}")
        
        if msg.type == 'note_on' and msg.velocity > 0:
            # Convert MIDI note to frequency (A4 = 69 = 440Hz)
            freq_val = 440.0 * (2 ** ((msg.note - 69) / 12))
            
            # Call synth engine note on method
            self.synth_engine.note_on(freq_val, msg.velocity / 127)
            self.current_note = msg.note
            self.update_status(f"Playing note: {msg.note} ({freq_val:.1f} Hz)")
            
        elif msg.type in ['note_off', 'note_on'] and msg.velocity == 0:
            if msg.note == self.current_note:
                # Call synth engine note off method
                self.synth_engine.note_off()
                self.current_note = None
                self.update_status("Ready")
    
    def setup_keyboard_fallback(self):
        """Set up computer keyboard for testing when MIDI isn't available"""
        try:
            # Access the keyboard event handler from pyo
            from pyo.lib._wxwidgets import KEYBOARD_FUNC
            
            def play_note(evt):
                if evt.char == 'a':
                    self.synth_engine.note_on(440, 0.7)  # A4 at 70% velocity
                    self.update_status("Playing note: A4 (440 Hz)")
                elif evt.char == 's':
                    self.synth_engine.note_off()
                    self.update_status("Note released")
                    
            # Attach to the server
            self.synth_engine.server._keyboardFunc = play_note
            self.update_status("Using keyboard fallback (press 'a' to play)")
        except Exception as e:
            print(f"Could not set up keyboard fallback: {e}")


class FMSynth:
    """Simple FM synthesizer with one carrier and one modulator"""
    
    def __init__(self):
        # Boot the audio server
        self.server = Server().boot()
        self.server.start()
        
        # === Control signals ===
        self.pitch = Sig(440.0)        # Base frequency
        self.velocity = Sig(0.0)       # MIDI velocity (0-1)
        
        # === FM Implementation with One Operator and One Carrier ===
        # Modulator parameters - relative mode (default)
        self.mod_ratio = Sig(2.0)       # Modulator/carrier frequency ratio
        self.mod_index = Sig(5.0)       # Modulation depth/index
        
        # Modulator parameters - fixed mode
        self.fixed_freq = Sig(880.0)    # Fixed frequency for modulator
        self.freq_offset = Sig(0.0)     # Frequency offset for relative mode
        
        # Modulator freq mode - 0=relative, 1=fixed
        self.freq_mode = 0
        
        # Carrier parameters
        self.carrier_intensity = Sig(1.0)  # Overall intensity/volume
        
        # Modulator envelope
        self.mod_env = Adsr(attack=0.01, decay=0.2, sustain=0.4, release=0.4, dur=1, mul=1.0)
        
        # Calculate modulator frequency differently based on mode
        # We'll use a Selector to switch between relative and fixed modes
        self.rel_freq = self.pitch * self.mod_ratio + self.freq_offset
        self.mod_freq_selector = Selector([self.rel_freq, self.fixed_freq])
        
        # Set initial mode (0 = relative)
        self.mod_freq_selector.voice = self.freq_mode
        
        # Scale modulation by index
        self.mod_amp = self.pitch * self.mod_index * self.mod_env
        self.modulator = Sine(freq=self.mod_freq_selector, mul=self.mod_amp)
        
        # Carrier with FM from modulator
        self.carrier_env = Adsr(attack=0.01, decay=0.1, sustain=0.8, release=0.5, dur=1, mul=0.25)
        self.carrier = Sine(
            freq=self.pitch + self.modulator, 
            mul=self.carrier_env * self.velocity * self.carrier_intensity
        )
        
        # Output
        self.carrier.out()
    
    def note_on(self, frequency, velocity):
        """Play a note with the given frequency and velocity"""
        self.pitch.value = frequency
        self.velocity.value = velocity
        
        # Trigger envelopes
        self.carrier_env.play()
        self.mod_env.play()
    
    def note_off(self):
        """Release the currently playing note"""
        self.carrier_env.stop()
        self.mod_env.stop()
    
    def set_operator_adsr(self, attack, decay, sustain, release):
        """Set the ADSR envelope for the operator/modulator"""
        self.mod_env.attack = attack
        self.mod_env.decay = decay
        self.mod_env.sustain = sustain
        self.mod_env.release = release
    
    def set_freq_mode(self, mode):
        """Set the frequency mode (0=relative, 1=fixed)"""
        self.freq_mode = mode
        self.mod_freq_selector.voice = mode


class FMSynthGUI(QMainWindow):
    """QT-based GUI for the FM synthesizer with tabbed interface"""
    
    def __init__(self, fm_synth, midi_controller):
        super().__init__()
        self.fm_synth = fm_synth
        self.midi_controller = midi_controller
        
        # Set up the main window
        self.setWindowTitle("Simple FM Synth")
        self.setGeometry(100, 100, 500, 500)
        
        # Create tabs
        self.tabs = QTabWidget()
        
        # Create carrier tab
        self.carrier_tab = QWidget()
        self.setup_carrier_tab()
        self.tabs.addTab(self.carrier_tab, "C")
        
        # Create operator tab
        self.operator_tab = QWidget()
        self.setup_operator_tab()
        self.tabs.addTab(self.operator_tab, "O1")
        
        # Set tabs as central widget
        self.setCentralWidget(self.tabs)
        
        # Set up MIDI status callback
        self.midi_controller.set_status_callback(self.update_midi_status)
        
        # Timer for UI updates
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(100)  # Update every 100ms
    
    def setup_carrier_tab(self):
        """Set up the carrier tab with intensity control and MIDI status"""
        layout = QVBoxLayout()
        
        # Carrier intensity slider (vertical)
        intensity_group = QGroupBox("Carrier Intensity")
        intensity_layout = QVBoxLayout()
        
        # Add spinbox for direct value entry
        self.intensity_spin = QDoubleSpinBox()
        self.intensity_spin.setRange(0.0, 2.0)
        self.intensity_spin.setValue(1.0)
        self.intensity_spin.setSingleStep(0.01)
        self.intensity_spin.valueChanged.connect(self.update_intensity_from_spin)
        intensity_layout.addWidget(self.intensity_spin, alignment=Qt.AlignHCenter)
        
        self.intensity_slider = QSlider(Qt.Vertical)
        self.intensity_slider.setMinimum(0)
        self.intensity_slider.setMaximum(200)
        self.intensity_slider.setValue(100)  # Default: 1.0
        self.intensity_slider.setMinimumHeight(200)
        self.intensity_slider.valueChanged.connect(self.update_intensity)
        intensity_layout.addWidget(self.intensity_slider, alignment=Qt.AlignHCenter)
        
        intensity_layout.addWidget(QLabel("Intensity"), alignment=Qt.AlignHCenter)
        intensity_group.setLayout(intensity_layout)
        
        # MIDI status
        midi_group = QGroupBox("MIDI Status")
        midi_layout = QVBoxLayout()
        self.midi_status_label = QLabel("Initializing...")
        midi_layout.addWidget(self.midi_status_label)
        midi_group.setLayout(midi_layout)
        
        # Add widgets to main layout
        layout.addWidget(intensity_group)
        layout.addWidget(midi_group)
        layout.addStretch(1)
        
        self.carrier_tab.setLayout(layout)
    
    def setup_operator_tab(self):
        """Set up the operator tab with frequency controls, index, and ADSR"""
        layout = QGridLayout()
        
        # Frequency mode selection
        freq_mode_group = QGroupBox("Frequency Mode")
        freq_mode_layout = QVBoxLayout()
        
        self.relative_mode_radio = QRadioButton("Relative")
        self.fixed_mode_radio = QRadioButton("Fixed")
        
        # Set relative mode as default
        self.relative_mode_radio.setChecked(True)
        
        # Create button group for mutual exclusivity
        self.freq_mode_group = QButtonGroup()
        self.freq_mode_group.addButton(self.relative_mode_radio, 0)  # 0 = relative
        self.freq_mode_group.addButton(self.fixed_mode_radio, 1)     # 1 = fixed
        self.freq_mode_group.buttonClicked.connect(self.frequency_mode_changed)
        
        freq_mode_layout.addWidget(self.relative_mode_radio)
        freq_mode_layout.addWidget(self.fixed_mode_radio)
        freq_mode_group.setLayout(freq_mode_layout)
        
        # Create stacked widget for the two frequency control modes
        freq_controls_group = QGroupBox("Frequency")
        freq_controls_layout = QVBoxLayout()
        
        # --- Relative frequency controls ---
        self.relative_controls = QWidget()
        relative_layout = QVBoxLayout()
        
        # Ratio spinbox and slider
        self.ratio_spin = QDoubleSpinBox()
        self.ratio_spin.setRange(0.1, 12.0)
        self.ratio_spin.setValue(2.0)
        self.ratio_spin.setSingleStep(0.1)
        self.ratio_spin.valueChanged.connect(self.update_ratio_from_spin)
        relative_layout.addWidget(self.ratio_spin, alignment=Qt.AlignHCenter)
        
        self.ratio_slider = QSlider(Qt.Vertical)
        self.ratio_slider.setMinimum(1)
        self.ratio_slider.setMaximum(120)
        self.ratio_slider.setValue(20)  # Default: 2.0
        self.ratio_slider.setMinimumHeight(150)
        self.ratio_slider.valueChanged.connect(self.update_ratio)
        relative_layout.addWidget(self.ratio_slider, alignment=Qt.AlignHCenter)
        relative_layout.addWidget(QLabel("Ratio"), alignment=Qt.AlignHCenter)
        
        # Offset spinbox and slider
        self.offset_spin = QSpinBox()
        self.offset_spin.setRange(-1000, 1000)
        self.offset_spin.setValue(0)
        self.offset_spin.setSingleStep(1)
        self.offset_spin.valueChanged.connect(self.update_offset_from_spin)
        relative_layout.addWidget(self.offset_spin, alignment=Qt.AlignHCenter)
        
        self.offset_slider = QSlider(Qt.Vertical)
        self.offset_slider.setMinimum(-1000)
        self.offset_slider.setMaximum(1000)
        self.offset_slider.setValue(0)  # Default: 0 Hz
        self.offset_slider.setMinimumHeight(150)
        self.offset_slider.valueChanged.connect(self.update_offset)
        relative_layout.addWidget(self.offset_slider, alignment=Qt.AlignHCenter)
        relative_layout.addWidget(QLabel("Offset (Hz)"), alignment=Qt.AlignHCenter)
        
        self.relative_controls.setLayout(relative_layout)
        
        # --- Fixed frequency controls ---
        self.fixed_controls = QWidget()
        fixed_layout = QVBoxLayout()
        
        # Fixed frequency spinbox and slider (logarithmic)
        self.fixed_freq_spin = QDoubleSpinBox()
        self.fixed_freq_spin.setRange(0.1, 20000.0)
        self.fixed_freq_spin.setValue(880.0)
        self.fixed_freq_spin.setSingleStep(0.1)
        self.fixed_freq_spin.setDecimals(1)
        self.fixed_freq_spin.valueChanged.connect(self.update_fixed_freq_from_spin)
        fixed_layout.addWidget(self.fixed_freq_spin, alignment=Qt.AlignHCenter)
        
        # Custom slider for logarithmic mapping (not truly logarithmic, but works well enough)
        self.fixed_freq_slider = QSlider(Qt.Vertical)
        self.fixed_freq_slider.setMinimum(1)  # 0.1 Hz
        self.fixed_freq_slider.setMaximum(500)  # Maps to 20000 Hz using log scaling
        self.fixed_freq_slider.setValue(self.freq_to_slider(880.0))
        self.fixed_freq_slider.setMinimumHeight(300)
        self.fixed_freq_slider.valueChanged.connect(self.update_fixed_freq)
        
        fixed_layout.addWidget(self.fixed_freq_slider, alignment=Qt.AlignHCenter)
        fixed_layout.addWidget(QLabel("Frequency (Hz)"), alignment=Qt.AlignHCenter)
        
        self.fixed_controls.setLayout(fixed_layout)
        
        # Add relative controls to layout (default)
        freq_controls_layout.addWidget(self.relative_controls)
        freq_controls_layout.addWidget(self.fixed_controls)
        self.fixed_controls.hide()
        
        freq_controls_group.setLayout(freq_controls_layout)
        
        # Index controls
        index_group = QGroupBox("Index")
        index_layout = QVBoxLayout()
        
        # Index spinbox and slider
        self.index_spin = QDoubleSpinBox()
        self.index_spin.setRange(0.0, 20.0)
        self.index_spin.setValue(5.0)
        self.index_spin.setSingleStep(0.1)
        self.index_spin.valueChanged.connect(self.update_index_from_spin)
        index_layout.addWidget(self.index_spin, alignment=Qt.AlignHCenter)
        
        self.index_slider = QSlider(Qt.Vertical)
        self.index_slider.setMinimum(0)
        self.index_slider.setMaximum(200)
        self.index_slider.setValue(50)  # Default: 5.0
        self.index_slider.setMinimumHeight(200)
        self.index_slider.valueChanged.connect(self.update_index)
        index_layout.addWidget(self.index_slider, alignment=Qt.AlignHCenter)
        
        index_layout.addWidget(QLabel("Index"), alignment=Qt.AlignHCenter)
        index_group.setLayout(index_layout)
        
        # ADSR controls
        adsr_group = QGroupBox("ADSR Envelope")
        adsr_layout = QGridLayout()
        
        # ADSR spinboxes
        self.attack_spin = QDoubleSpinBox()
        self.attack_spin.setRange(0.001, 1.0)
        self.attack_spin.setValue(0.01)
        self.attack_spin.setSingleStep(0.01)
        self.attack_spin.setDecimals(3)
        self.attack_spin.valueChanged.connect(self.update_adsr_from_spin)
        
        self.decay_spin = QDoubleSpinBox()
        self.decay_spin.setRange(0.001, 1.0)
        self.decay_spin.setValue(0.2)
        self.decay_spin.setSingleStep(0.01)
        self.decay_spin.setDecimals(3)
        self.decay_spin.valueChanged.connect(self.update_adsr_from_spin)
        
        self.sustain_spin = QDoubleSpinBox()
        self.sustain_spin.setRange(0.0, 1.0)
        self.sustain_spin.setValue(0.4)
        self.sustain_spin.setSingleStep(0.01)
        self.sustain_spin.setDecimals(2)
        self.sustain_spin.valueChanged.connect(self.update_adsr_from_spin)
        
        self.release_spin = QDoubleSpinBox()
        self.release_spin.setRange(0.001, 1.0)
        self.release_spin.setValue(0.4)
        self.release_spin.setSingleStep(0.01)
        self.release_spin.setDecimals(3)
        self.release_spin.valueChanged.connect(self.update_adsr_from_spin)
        
        # Create ADSR sliders
        self.attack_slider = QSlider(Qt.Vertical)
        self.attack_slider.setMinimum(1)
        self.attack_slider.setMaximum(1000)
        self.attack_slider.setValue(10)  # Default: 0.01
        self.attack_slider.setMinimumHeight(200)
        self.attack_slider.valueChanged.connect(self.update_adsr)
        
        self.decay_slider = QSlider(Qt.Vertical)
        self.decay_slider.setMinimum(1)
        self.decay_slider.setMaximum(1000)
        self.decay_slider.setValue(200)  # Default: 0.2
        self.decay_slider.setMinimumHeight(200)
        self.decay_slider.valueChanged.connect(self.update_adsr)
        
        self.sustain_slider = QSlider(Qt.Vertical)
        self.sustain_slider.setMinimum(0)
        self.sustain_slider.setMaximum(100)
        self.sustain_slider.setValue(40)  # Default: 0.4
        self.sustain_slider.setMinimumHeight(200)
        self.sustain_slider.valueChanged.connect(self.update_adsr)
        
        self.release_slider = QSlider(Qt.Vertical)
        self.release_slider.setMinimum(1)
        self.release_slider.setMaximum(1000)
        self.release_slider.setValue(400)  # Default: 0.4
        self.release_slider.setMinimumHeight(200)
        self.release_slider.valueChanged.connect(self.update_adsr)
        
        # Add spinboxes to grid
        adsr_layout.addWidget(self.attack_spin, 0, 0, alignment=Qt.AlignHCenter)
        adsr_layout.addWidget(self.decay_spin, 0, 1, alignment=Qt.AlignHCenter)
        adsr_layout.addWidget(self.sustain_spin, 0, 2, alignment=Qt.AlignHCenter)
        adsr_layout.addWidget(self.release_spin, 0, 3, alignment=Qt.AlignHCenter)
        
        # Add sliders to grid
        adsr_layout.addWidget(self.attack_slider, 1, 0, alignment=Qt.AlignHCenter)
        adsr_layout.addWidget(self.decay_slider, 1, 1, alignment=Qt.AlignHCenter)
        adsr_layout.addWidget(self.sustain_slider, 1, 2, alignment=Qt.AlignHCenter)
        adsr_layout.addWidget(self.release_slider, 1, 3, alignment=Qt.AlignHCenter)
        
        # Add labels
        adsr_layout.addWidget(QLabel("A"), 2, 0, alignment=Qt.AlignHCenter)
        adsr_layout.addWidget(QLabel("D"), 2, 1, alignment=Qt.AlignHCenter)
        adsr_layout.addWidget(QLabel("S"), 2, 2, alignment=Qt.AlignHCenter)
        adsr_layout.addWidget(QLabel("R"), 2, 3, alignment=Qt.AlignHCenter)
        
        adsr_group.setLayout(adsr_layout)
        
        # Add widgets to main grid layout
        layout.addWidget(freq_mode_group, 0, 0)
        layout.addWidget(freq_controls_group, 1, 0)
        layout.addWidget(index_group, 0, 1, 2, 1)
        layout.addWidget(adsr_group, 0, 2, 2, 2)
        
        self.operator_tab.setLayout(layout)
    
    def frequency_mode_changed(self, button):
        """Handle change of frequency mode"""
        mode = self.freq_mode_group.id(button)
        self.fm_synth.set_freq_mode(mode)
        
        # Update UI
        if mode == 0:  # Relative mode
            self.fixed_controls.hide()
            self.relative_controls.show()
        else:  # Fixed mode
            self.relative_controls.hide()
            self.fixed_controls.show()
    
    def freq_to_slider(self, freq):
        """Convert a frequency value to a slider position using pseudo-logarithmic mapping"""
        # For frequencies 0.1 to 20Hz, map to slider positions 1-100
        if freq <= 20:
            return int(1 + (freq - 0.1) * 99 / 19.9)
        # For frequencies 20 to 200Hz, map to slider positions 100-200
        elif freq <= 200:
            return int(100 + (freq - 20) * 100 / 180)
        # For frequencies 200 to 2000Hz, map to slider positions 200-300
        elif freq <= 2000:
            return int(200 + (freq - 200) * 100 / 1800)
        # For frequencies 2000 to 20000Hz, map to slider positions 300-500
        else:
            return int(300 + (freq - 2000) * 200 / 18000)
    
    def slider_to_freq(self, pos):
        """Convert a slider position to a frequency value using pseudo-logarithmic mapping"""
        # For slider positions 1-100, map to frequencies 0.1 to 20Hz
        if pos <= 100:
            return 0.1 + (pos - 1) * 19.9 / 99
        # For slider positions 100-200, map to frequencies 20 to 200Hz
        elif pos <= 200:
            return 20 + (pos - 100) * 180 / 100
        # For slider positions 200-300, map to frequencies 200 to 2000Hz
        elif pos <= 300:
            return 200 + (pos - 200) * 1800 / 100
        # For slider positions 300-500, map to frequencies 2000 to 20000Hz
        else:
            return 2000 + (pos - 300) * 18000 / 200
    
    def update_intensity(self):
        """Update the carrier intensity from slider"""
        value = self.intensity_slider.value() / 100
        self.fm_synth.carrier_intensity.value = value
        # Update spinbox without triggering another update
        self.intensity_spin.blockSignals(True)
        self.intensity_spin.setValue(value)
        self.intensity_spin.blockSignals(False)
    
    def update_intensity_from_spin(self):
        """Update the carrier intensity from spinbox"""
        value = self.intensity_spin.value()
        self.fm_synth.carrier_intensity.value = value
        # Update slider without triggering another update
        self.intensity_slider.blockSignals(True)
        self.intensity_slider.setValue(int(value * 100))
        self.intensity_slider.blockSignals(False)
    
    def update_ratio(self):
        """Update the modulator frequency ratio from slider"""
        value = self.ratio_slider.value() / 10
        self.fm_synth.mod_ratio.value = value
        # Update spinbox without triggering another update
        self.ratio_spin.blockSignals(True)
        self.ratio_spin.setValue(value)
        self.ratio_spin.blockSignals(False)
    
    def update_ratio_from_spin(self):
        """Update the modulator frequency ratio from spinbox"""
        value = self.ratio_spin.value()
        self.fm_synth.mod_ratio.value = value
        # Update slider without triggering another update
        self.ratio_slider.blockSignals(True)
        self.ratio_slider.setValue(int(value * 10))
        self.ratio_slider.blockSignals(False)
    
    def update_offset(self):
        """Update the frequency offset from slider"""
        value = self.offset_slider.value()
        self.fm_synth.freq_offset.value = value
        # Update spinbox without triggering another update
        self.offset_spin.blockSignals(True)
        self.offset_spin.setValue(value)
        self.offset_spin.blockSignals(False)
    
    def update_offset_from_spin(self):
        """Update the frequency offset from spinbox"""
        value = self.offset_spin.value()
        self.fm_synth.freq_offset.value = value
        # Update slider without triggering another update
        self.offset_slider.blockSignals(True)
        self.offset_slider.setValue(value)
        self.offset_slider.blockSignals(False)
    
    def update_fixed_freq(self):
        """Update the fixed frequency from slider using log mapping"""
        slider_pos = self.fixed_freq_slider.value()
        freq = self.slider_to_freq(slider_pos)
        self.fm_synth.fixed_freq.value = freq
        # Update spinbox without triggering another update
        self.fixed_freq_spin.blockSignals(True)
        self.fixed_freq_spin.setValue(freq)
        self.fixed_freq_spin.blockSignals(False)
    
    def update_fixed_freq_from_spin(self):
        """Update the fixed frequency from spinbox"""
        freq = self.fixed_freq_spin.value()
        self.fm_synth.fixed_freq.value = freq
        # Update slider without triggering another update
        slider_pos = self.freq_to_slider(freq)
        self.fixed_freq_slider.blockSignals(True)
        self.fixed_freq_slider.setValue(slider_pos)
        self.fixed_freq_slider.blockSignals(False)
    
    def update_index(self):
        """Update the modulation index from slider"""
        value = self.index_slider.value() / 10
        self.fm_synth.mod_index.value = value
        # Update spinbox without triggering another update
        self.index_spin.blockSignals(True)
        self.index_spin.setValue(value)
        self.index_spin.blockSignals(False)
    
    def update_index_from_spin(self):
        """Update the modulation index from spinbox"""
        value = self.index_spin.value()
        self.fm_synth.mod_index.value = value
        # Update slider without triggering another update
        self.index_slider.blockSignals(True)
        self.index_slider.setValue(int(value * 10))
        self.index_slider.blockSignals(False)
    
    def update_adsr_from_spin(self):
        """Update the operator ADSR envelope from spinboxes"""
        attack = self.attack_spin.value()
        decay = self.decay_spin.value()
        sustain = self.sustain_spin.value()
        release = self.release_spin.value()
        
        self.fm_synth.set_operator_adsr(attack, decay, sustain, release)
        
        # Update sliders without triggering another update
        self.attack_slider.blockSignals(True)
        self.decay_slider.blockSignals(True)
        self.sustain_slider.blockSignals(True)
        self.release_slider.blockSignals(True)
        
        self.attack_slider.setValue(int(attack * 1000))
        self.decay_slider.setValue(int(decay * 1000))
        self.sustain_slider.setValue(int(sustain * 100))
        self.release_slider.setValue(int(release * 1000))
        
        self.attack_slider.blockSignals(False)
        self.decay_slider.blockSignals(False)
        self.sustain_slider.blockSignals(False)
        self.release_slider.blockSignals(False)
    
    def update_adsr(self):
        """Update the operator ADSR envelope from sliders"""
        attack = self.attack_slider.value() / 1000
        decay = self.decay_slider.value() / 1000
        sustain = self.sustain_slider.value() / 100
        release = self.release_slider.value() / 1000
        
        self.fm_synth.set_operator_adsr(attack, decay, sustain, release)
        
        # Update spinboxes without triggering another update
        self.attack_spin.blockSignals(True)
        self.decay_spin.blockSignals(True)
        self.sustain_spin.blockSignals(True)
        self.release_spin.blockSignals(True)
        
        self.attack_spin.setValue(attack)
        self.decay_spin.setValue(decay)
        self.sustain_spin.setValue(sustain)
        self.release_spin.setValue(release)
        
        self.attack_spin.blockSignals(False)
        self.decay_spin.blockSignals(False)
        self.sustain_spin.blockSignals(False)
        self.release_spin.blockSignals(False)
    
    def update_midi_status(self, status):
        """Update the MIDI status label"""
        self.midi_status_label.setText(status)
    
    def update_ui(self):
        """Update UI elements periodically"""
        # This method can be used for real-time updates if needed
        pass


# Main program
if __name__ == "__main__":
    # Create the app
    app = QApplication(sys.argv)
    
    # Create the FM synth
    fm_synth = FMSynth()
    
    # Create MIDI controller
    midi_controller = MidiController(fm_synth)
    
    # Create the GUI
    gui = FMSynthGUI(fm_synth, midi_controller)
    gui.show()
    
    # Start MIDI controller
    midi_controller.start()
    
    # Start audio server GUI for visualization and control
    fm_synth.server.gui(locals())
    
    # Run the Qt event loop
    sys.exit(app.exec_())
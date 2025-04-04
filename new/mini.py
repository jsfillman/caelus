from pyo import *
import mido
from threading import Thread
import multiprocessing as mp
import numpy as np
import time
import sys
from numba import jit
from PyQt5.QtWidgets import (QApplication, QMainWindow, QSlider, QVBoxLayout, QHBoxLayout, 
                            QLabel, QWidget, QTabWidget, QGroupBox, QGridLayout, 
                            QRadioButton, QButtonGroup, QDoubleSpinBox, QSpinBox)
from PyQt5.QtCore import Qt, QTimer


# === NUMBA OPTIMIZED FUNCTIONS ===
@jit(nopython=True)
def calculate_fm_modulation(carrier_freq, mod_freq, mod_index):
    """Calculate FM modulation (optimized with Numba)"""
    # This is a simplified example - would be expanded for complex FM routing
    return carrier_freq + mod_freq * mod_index


# === PARTICLE PROCESS ===
class FMParticle(mp.Process):
    """A single FM synthesis particle running in its own process"""
    
    def __init__(self, cmd_queue, audio_queue, particle_id=0):
        super().__init__()
        self.cmd_queue = cmd_queue        # For receiving control messages
        self.audio_queue = audio_queue    # For sending audio data if needed
        self.particle_id = particle_id
        self.running = mp.Value('b', True)
        
        # Shared memory for key parameters (can be accessed by main process)
        self.current_pitch = mp.Value('d', 440.0)  # Double precision float
    
    def run(self):
        """Main process function"""
        try:
            # Initialize audio components within this process
            self.server = Server(audio='portaudio')  # Use PortAudio for flexibility
            self.server.setInOutDevice(0)  # Use default device
            self.server.boot()
            
            # Create sine table (shared among all oscillators for efficiency)
            self.sine_table = HarmTable([1], size=8192)
            
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
            
            # Use HarmTable for modulator (more efficient than Sine)
            self.modulator = Osc(table=self.sine_table, freq=self.mod_freq_selector, mul=self.mod_amp)
            
            # Carrier with FM from modulator
            self.carrier_env = Adsr(attack=0.01, decay=0.1, sustain=0.8, release=0.5, dur=1, mul=0.25)
            
            # Use HarmTable for carrier (more efficient than Sine)
            self.carrier = Osc(
                table=self.sine_table,
                freq=self.pitch + self.modulator, 
                mul=self.carrier_env * self.velocity * self.carrier_intensity
            )
            
            # Output with panning (center by default)
            self.panner = Pan(self.carrier, outs=2, pan=0.5)
            self.panner.out()
            
            # Start audio processing
            self.server.start()
            
            print(f"Particle {self.particle_id} started")
            
            # Process control messages until stopped
            while self.running.value:
                if not self.cmd_queue.empty():
                    msg = self.cmd_queue.get()
                    self.process_message(msg)
                
                # Sleep a bit to prevent CPU hogging
                time.sleep(0.001)
            
            # Cleanup when stopped
            self.server.stop()
            
        except Exception as e:
            print(f"Error in particle {self.particle_id}: {e}")
    
    def process_message(self, msg):
        """Process a control message from the main process"""
        cmd = msg.get('cmd', '')
        
        if cmd == 'note_on':
            freq = msg.get('freq', 440.0)
            vel = msg.get('vel', 0.7)
            self.note_on(freq, vel)
            
        elif cmd == 'note_off':
            self.note_off()
            
        elif cmd == 'set_param':
            param = msg.get('param', '')
            value = msg.get('value', 0)
            self.set_parameter(param, value)
            
        elif cmd == 'set_freq_mode':
            mode = msg.get('mode', 0)
            self.mod_freq_selector.voice = mode
    
    def note_on(self, freq, vel):
        """Play a note with the given frequency and velocity"""
        self.pitch.value = freq
        self.current_pitch.value = freq  # Update shared memory
        self.velocity.value = vel
        
        # Trigger envelopes
        self.carrier_env.play()
        self.mod_env.play()
    
    def note_off(self):
        """Release the currently playing note"""
        self.carrier_env.stop()
        self.mod_env.stop()
    
    def set_parameter(self, param, value):
        """Set a synth parameter"""
        if param == 'ratio':
            self.mod_ratio.value = value
        elif param == 'index':
            self.mod_index.value = value
        elif param == 'fixed_freq':
            self.fixed_freq.value = value
        elif param == 'offset':
            self.freq_offset.value = value
        elif param == 'intensity':
            self.carrier_intensity.value = value
        elif param == 'attack':
            self.mod_env.attack = value
        elif param == 'decay':
            self.mod_env.decay = value
        elif param == 'sustain':
            self.mod_env.sustain = value
        elif param == 'release':
            self.mod_env.release = value


# === MASTER SYNTH CONTROLLER ===
class FMSynthMaster:
    """Master class that manages multiple FM particles"""
    
    def __init__(self, num_particles=1):
        # Create queues for communication with particles
        self.cmd_queues = []
        self.audio_queues = []
        
        # Create and start particles
        self.particles = []
        for i in range(num_particles):
            cmd_q = mp.Queue()
            audio_q = mp.Queue()
            
            particle = FMParticle(cmd_q, audio_q, particle_id=i)
            particle.daemon = True  # Make sure process terminates when main program exits
            particle.start()
            
            self.cmd_queues.append(cmd_q)
            self.audio_queues.append(audio_q)
            self.particles.append(particle)
        
        # Store current notes for each particle
        self.current_notes = [None] * num_particles
    
    def note_on(self, note, velocity, particle_idx=0):
        """Send note on message to a specific particle"""
        if 0 <= particle_idx < len(self.cmd_queues):
            # Convert MIDI note to frequency
            freq = 440.0 * (2 ** ((note - 69) / 12))
            
            self.cmd_queues[particle_idx].put({
                'cmd': 'note_on',
                'freq': freq,
                'vel': velocity / 127.0
            })
            self.current_notes[particle_idx] = note
    
    def note_off(self, note, particle_idx=0):
        """Send note off message to a specific particle if it's playing this note"""
        if 0 <= particle_idx < len(self.cmd_queues) and self.current_notes[particle_idx] == note:
            self.cmd_queues[particle_idx].put({
                'cmd': 'note_off'
            })
            self.current_notes[particle_idx] = None
    
    def set_parameter(self, param, value, particle_idx=0):
        """Set a parameter on a specific particle"""
        if 0 <= particle_idx < len(self.cmd_queues):
            self.cmd_queues[particle_idx].put({
                'cmd': 'set_param',
                'param': param,
                'value': value
            })
    
    def set_freq_mode(self, mode, particle_idx=0):
        """Set frequency mode on a specific particle"""
        if 0 <= particle_idx < len(self.cmd_queues):
            self.cmd_queues[particle_idx].put({
                'cmd': 'set_freq_mode',
                'mode': mode
            })
    
    def shutdown(self):
        """Shutdown all particles"""
        for particle in self.particles:
            particle.running.value = False
        
        for particle in self.particles:
            if particle.is_alive():
                particle.join(timeout=1.0)


# === MIDI CONTROLLER ===
class MidiController:
    """Handles MIDI input/output functionality"""
    
    def __init__(self, synth_master):
        """Initialize MIDI controller with reference to synth master"""
        self.synth_master = synth_master
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
            print("Playing without MIDI. Use computer keyboard to test.")
            
            # Set up keyboard handler as fallback
            self.setup_keyboard_fallback()
    
    def process_midi_message(self, msg):
        """Process incoming MIDI messages"""
        print(f"MIDI: {msg}")
        
        if msg.type == 'note_on' and msg.velocity > 0:
            # Send to first particle for now
            self.synth_master.note_on(msg.note, msg.velocity, particle_idx=0)
            self.current_note = msg.note
            
            # Convert MIDI note to frequency for display
            freq_val = 440.0 * (2 ** ((msg.note - 69) / 12))
            self.update_status(f"Playing note: {msg.note} ({freq_val:.1f} Hz)")
            
        elif msg.type in ['note_off', 'note_on'] and msg.velocity == 0:
            # Send to first particle for now
            self.synth_master.note_off(msg.note, particle_idx=0)
            if msg.note == self.current_note:
                self.current_note = None
                self.update_status("Ready")
    
    def setup_keyboard_fallback(self):
        """Set up computer keyboard for testing when MIDI isn't available"""
        print("Keyboard fallback enabled - press 'a' to play a note, 's' to stop")


# === GUI CLASS ===
class FMSynthGUI(QMainWindow):
    """QT-based GUI for the FM synthesizer with tabbed interface"""
    
    def __init__(self, synth_master, midi_controller):
        super().__init__()
        self.synth_master = synth_master
        self.midi_controller = midi_controller
        
        # Set up the main window
        self.setWindowTitle("Multi-Particle FM Synth")
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
        
        # Custom slider for logarithmic mapping
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
        self.synth_master.set_freq_mode(mode, particle_idx=0)
        
        # Update UI
        if mode == 0:  # Relative mode
            self.fixed_controls.hide()
            self.relative_controls.show()
        else:  # Fixed mode
            self.relative_controls.hide()
            self.fixed_controls.show()
    
    # === Utility methods for frequency slider ===
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
            return min(500, int(300 + (freq - 2000) * 200 / 18000))
    
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
    
    # === Parameter update methods ===
    def update_intensity(self):
        """Update the carrier intensity from slider"""
        value = self.intensity_slider.value() / 100
        self.synth_master.set_parameter('intensity', value, particle_idx=0)
        # Update spinbox without triggering another update
        self.intensity_spin.blockSignals(True)
        self.intensity_spin.setValue(value)
        self.intensity_spin.blockSignals(False)
    
    def update_intensity_from_spin(self):
        """Update the carrier intensity from spinbox"""
        value = self.intensity_spin.value()
        self.synth_master.set_parameter('intensity', value, particle_idx=0)
        # Update slider without triggering another update
        self.intensity_slider.blockSignals(True)
        self.intensity_slider.setValue(int(value * 100))
        self.intensity_slider.blockSignals(False)
    
    def update_ratio(self):
        """Update the modulator frequency ratio from slider"""
        value = self.ratio_slider.value() / 10
        self.synth_master.set_parameter('ratio', value, particle_idx=0)
        # Update spinbox without triggering another update
        self.ratio_spin.blockSignals(True)
        self.ratio_spin.setValue(value)
        self.ratio_spin.blockSignals(False)
    
    def update_ratio_from_spin(self):
        """Update the modulator frequency ratio from spinbox"""
        value = self.ratio_spin.value()
        self.synth_master.set_parameter('ratio', value, particle_idx=0)
        # Update slider without triggering another update
        self.ratio_slider.blockSignals(True)
        self.ratio_slider.setValue(int(value * 10))
        self.ratio_slider.blockSignals(False)
    
    def update_offset(self):
        """Update the frequency offset from slider"""
        value = self.offset_slider.value()
        self.synth_master.set_parameter('offset', value, particle_idx=0)
        # Update spinbox without triggering another update
        self.offset_spin.blockSignals(True)
        self.offset_spin.setValue(value)
        self.offset_spin.blockSignals(False)
    
    def update_offset_from_spin(self):
        """Update the frequency offset from spinbox"""
        value = self.offset_spin.value()
        self.synth_master.set_parameter('offset', value, particle_idx=0)
        # Update slider without triggering another update
        self.offset_slider.blockSignals(True)
        self.offset_slider.setValue(value)
        self.offset_slider.blockSignals(False)
    
    def update_fixed_freq(self):
        """Update the fixed frequency from slider using log mapping"""
        slider_pos = self.fixed_freq_slider.value()
        freq = self.slider_to_freq(slider_pos)
        self.synth_master.set_parameter('fixed_freq', freq, particle_idx=0)
        # Update spinbox without triggering another update
        self.fixed_freq_spin.blockSignals(True)
        self.fixed_freq_spin.setValue(freq)
        self.fixed_freq_spin.blockSignals(False)
    
    def update_fixed_freq_from_spin(self):
        """Update the fixed frequency from spinbox"""
        freq = self.fixed_freq_spin.value()
        self.synth_master.set_parameter('fixed_freq', freq, particle_idx=0)
        # Update slider without triggering another update
        slider_pos = self.freq_to_slider(freq)
        self.fixed_freq_slider.blockSignals(True)
        self.fixed_freq_slider.setValue(slider_pos)
        self.fixed_freq_slider.blockSignals(False)
    
    def update_index(self):
        """Update the modulation index from slider"""
        value = self.index_slider.value() / 10
        self.synth_master.set_parameter('index', value, particle_idx=0)
        # Update spinbox without triggering another update
        self.index_spin.blockSignals(True)
        self.index_spin.setValue(value)
        self.index_spin.blockSignals(False)
    
    def update_index_from_spin(self):
        """Update the modulation index from spinbox"""
        value = self.index_spin.value()
        self.synth_master.set_parameter('index', value, particle_idx=0)
        # Update slider without triggering another update
        self.index_slider.blockSignals(True)
        self.index_slider.setValue(int(value * 10))
        self.index_slider.blockSignals(False)
    
    def update_adsr(self):
        """Update the operator ADSR envelope from sliders"""
        attack = self.attack_slider.value() / 1000
        decay = self.decay_slider.value() / 1000
        sustain = self.sustain_slider.value() / 100
        release = self.release_slider.value() / 1000
        
        # Send individual parameter updates
        self.synth_master.set_parameter('attack', attack, particle_idx=0)
        self.synth_master.set_parameter('decay', decay, particle_idx=0)
        self.synth_master.set_parameter('sustain', sustain, particle_idx=0)
        self.synth_master.set_parameter('release', release, particle_idx=0)
        
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
    
    def update_adsr_from_spin(self):
        """Update the operator ADSR envelope from spinboxes"""
        attack = self.attack_spin.value()
        decay = self.decay_spin.value()
        sustain = self.sustain_spin.value()
        release = self.release_spin.value()
        
        # Send individual parameter updates
        self.synth_master.set_parameter('attack', attack, particle_idx=0)
        self.synth_master.set_parameter('decay', decay, particle_idx=0)
        self.synth_master.set_parameter('sustain', sustain, particle_idx=0)
        self.synth_master.set_parameter('release', release, particle_idx=0)
        
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
    
    def update_midi_status(self, status):
        """Update the MIDI status label"""
        self.midi_status_label.setText(status)
    
    def update_ui(self):
        """Update UI elements periodically"""
        # This method can be used for real-time updates if needed
        pass
    
    def closeEvent(self, event):
        """Handle window close event"""
        # Clean up resources when the window is closed
        print("Shutting down synth engine...")
        self.synth_master.shutdown()
        event.accept()


# === Main program ===
if __name__ == "__main__":
    # Enable multiprocessing support on Windows
    if sys.platform.startswith('win'):
        mp.freeze_support()
    
    try:
        # Create the app
        app = QApplication(sys.argv)
        
        # Create the FM synth master with one particle to start
        synth_master = FMSynthMaster(num_particles=1)
        
        # Create MIDI controller
        midi_controller = MidiController(synth_master)
        
        # Create the GUI
        gui = FMSynthGUI(synth_master, midi_controller)
        gui.show()
        
        # Start MIDI controller
        midi_controller.start()
        
        # Run the Qt event loop
        sys.exit(app.exec_())
        
    except Exception as e:
        print(f"Error in main program: {e}")
        
    finally:
        # Make sure synth is properly shut down
        if 'synth_master' in locals():
            synth_master.shutdown()
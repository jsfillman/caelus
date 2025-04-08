import pyo
import mido
import random
import atexit
import sys

from PyQt5.QtWidgets import (
    QApplication, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, 
    QComboBox, QLabel, QPushButton, QGroupBox, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer

from oscillator_ui import OscillatorUI
from wavetables import WaveformBank
from settings import load_patch, save_patch
from particle import Particle
from midi_handler import MidiHandler

# Default patch file with absolute path
import os
PATCH_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "last_patch.yaml")

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Caelux Mini")
        
        # Initialize audio server
        self.server = None
        self.init_audio_server()
        
        # Initialize the Particle (which contains 2 oscillators)
        self.particle = Particle(self.server)
        
        # Initialize the MIDI handler
        self.midi_handler = MidiHandler()
        
        # Connect MIDI signals to particle
        self.connect_midi_to_particle()
        
        # Create main layout
        main_layout = QHBoxLayout()
        
        # Create tab widget for vertical tabs
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.West)  # Put tabs on the left side
        
        # Add Global tab
        global_tab = self.create_global_tab()
        self.tabs.addTab(global_tab, "G")
        self.tabs.setTabToolTip(0, "Global Settings")
        
        # Add Operator tab (OP1)
        self.op1_ui = OscillatorUI(self.server, "OP1", "operator")
        self.tabs.addTab(self.op1_ui, "O1")
        self.tabs.setTabToolTip(1, "Operator 1")
        
        # Add Carrier tab (CAR1)
        self.car1_ui = OscillatorUI(self.server, "CAR1", "carrier")
        self.tabs.addTab(self.car1_ui, "C1")
        self.tabs.setTabToolTip(2, "Carrier 1")
        
        # Connect bypass signals to oscillator methods
        self.connect_bypass_signals()
        
        main_layout.addWidget(self.tabs)
        self.setLayout(main_layout)
        
        # Set the window size
        self.setMinimumWidth(1500)
        self.setMinimumHeight(800)
        
        # Try to load the last patch if available
        try:
            if os.path.exists(PATCH_FILE):
                self.load_patch()
        except Exception as e:
            print(f"Could not load last patch: {e}")
        
        # Register function to save patch on exit
        atexit.register(self.save_on_exit)
    
    def connect_midi_to_particle(self):
        """Connect MIDI handler signals to particle methods"""
        if not hasattr(self, 'midi_handler') or not hasattr(self, 'particle'):
            return
            
        # Connect note signals
        self.midi_handler.note_on_signal.connect(self.handle_note_on)
        self.midi_handler.note_off_signal.connect(self.particle.note_off)
        
        # Connect other MIDI signals as needed
        self.midi_handler.pitch_bend_signal.connect(self.particle.pitch_bend)
        
    def connect_bypass_signals(self):
        """Connect UI bypass signals to oscillator bypass methods"""
        if not hasattr(self, 'particle') or not self.particle.initialized:
            return
            
        # Connect OP1 bypass signals
        if "OP1" in self.particle.oscillators:
            op1 = self.particle.oscillators["OP1"]
            self.op1_ui.osc_bypass_toggled.connect(lambda state: op1.set_bypass('osc', state))
            self.op1_ui.freq_bypass_toggled.connect(lambda state: op1.set_bypass('freq', state))
            self.op1_ui.amp_bypass_toggled.connect(lambda state: op1.set_bypass('amp', state))
            self.op1_ui.filter_bypass_toggled.connect(lambda state: op1.set_bypass('filter', state))
            self.op1_ui.delay_bypass_toggled.connect(lambda state: op1.set_bypass('delay', state))
            
            # Connect panner signals
            self.op1_ui.pan_position_changed_signal.connect(op1.set_pan_position)
            self.op1_ui.stereo_width_changed_signal.connect(op1.set_stereo_width)
            self.op1_ui.autopan_toggled_signal.connect(lambda enabled: op1.set_autopan(enabled))
            self.op1_ui.autopan_rate_changed_signal.connect(lambda rate: op1.set_autopan(op1.use_autopan, rate))
            
        # Connect CAR1 bypass signals
        if "CAR1" in self.particle.oscillators:
            car1 = self.particle.oscillators["CAR1"]
            self.car1_ui.osc_bypass_toggled.connect(lambda state: car1.set_bypass('osc', state))
            self.car1_ui.freq_bypass_toggled.connect(lambda state: car1.set_bypass('freq', state))
            self.car1_ui.amp_bypass_toggled.connect(lambda state: car1.set_bypass('amp', state))
            self.car1_ui.filter_bypass_toggled.connect(lambda state: car1.set_bypass('filter', state))
            self.car1_ui.delay_bypass_toggled.connect(lambda state: car1.set_bypass('delay', state))
            
            # Connect panner signals
            self.car1_ui.pan_position_changed_signal.connect(car1.set_pan_position)
            self.car1_ui.stereo_width_changed_signal.connect(car1.set_stereo_width)
            self.car1_ui.autopan_toggled_signal.connect(lambda enabled: car1.set_autopan(enabled))
            self.car1_ui.autopan_rate_changed_signal.connect(lambda rate: car1.set_autopan(car1.use_autopan, rate))
    
    def handle_note_on(self, note, velocity):
        """Handle note on by passing parameters from UI"""
        # Create a dictionary of UI references for each oscillator
        ui_dict = {
            "OP1": self.op1_ui,
            "CAR1": self.car1_ui
        }
        
        # Trigger note-on on the particle with UI references
        self.particle.note_on(note, velocity, ui_dict)
    
    def init_audio_server(self):
        """Initialize audio server with default settings"""
        try:
            # Start with default settings
            self.server = pyo.Server()
            
            # Try to boot and start the server
            self.server.boot()
            self.server.start()
            
            # Print current audio settings for debugging
            print(f"Audio initialized - SR: {self.server.getSamplingRate()}, BS: {self.server.getBufferSize()}")
            
            # Print the current output device for debugging
            try:
                current_device = self.server.getDefaultOutputDevice()
                print(f"Current output device index: {current_device}")
            except Exception as e:
                print(f"Could not get default output device: {e}")
                
        except Exception as e:
            QMessageBox.warning(self, "Audio Error", 
                f"Could not start audio server: {e}\n\nThe synthesizer will not produce sound.")
            self.server = None
    
    def create_global_tab(self):
        """Create the Global settings tab with audio and MIDI selections"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Audio Output Selection
        audio_group = QGroupBox("Audio Output")
        audio_layout = QVBoxLayout()
        
        self.audio_devices_label = QLabel("Audio Output Device:")
        self.audio_devices = QComboBox()
        
        # Get available audio outputs from pyo
        if self.server:
            try:
                # Get audio devices using custom parsing based on debug output
                audio_info = pyo.pa_get_devices_infos()
                output_devices = []
                
                # Special case handling for macOS format based on debug output
                for i, dev in enumerate(audio_info):
                    # Look for devices with 'latency' key in full info
                    for key, value in dev.items():
                        if isinstance(value, dict) and 'name' in value and 'latency' in value:
                            # This looks like an output device entry
                            if 'Output' in value['name'] or 'Audio' in value['name']:
                                name = value['name']
                                # Use the key as the device index
                                device_index = int(key)
                                output_devices.append((device_index, name))
                
                # If we didn't find any devices with the above method, try a simpler approach
                if not output_devices:
                    for i, dev in enumerate(audio_info):
                        output_devices.append((i, f"Audio Device {i}"))
                
                # Add the devices to the dropdown
                for i, name in output_devices:
                    self.audio_devices.addItem(name, i)  # Store device index as user data
                
                # Default to first device if available
                if self.audio_devices.count() > 0:
                    self.audio_devices.setCurrentIndex(0)
                    print(f"Set default audio device to: {self.audio_devices.currentText()}")
                
            except Exception as e:
                print(f"Error getting audio devices: {e}")
                self.audio_devices.addItem("Error listing audio devices")
        else:
            self.audio_devices.addItem("No audio devices detected")
        
        self.audio_devices.currentIndexChanged.connect(self.change_audio_device)
        
        audio_layout.addWidget(self.audio_devices_label)
        audio_layout.addWidget(self.audio_devices)
        
        # Sample rate and buffer size
        audio_info_layout = QHBoxLayout()
        
        self.sample_rate_label = QLabel("Sample Rate:")
        self.sample_rate = QComboBox()
        self.sample_rate.addItems(["44100", "48000", "96000"])
        if self.server:
            current_sr = str(int(self.server.getSamplingRate()))
            index = self.sample_rate.findText(current_sr)
            if index >= 0:
                self.sample_rate.setCurrentIndex(index)
        
        self.buffer_size_label = QLabel("Buffer Size:")
        self.buffer_size = QComboBox()
        self.buffer_size.addItems(["64", "128", "256", "512", "1024", "2048"])
        if self.server:
            current_bs = str(self.server.getBufferSize())
            index = self.buffer_size.findText(current_bs)
            if index >= 0:
                self.buffer_size.setCurrentIndex(index)
        
        audio_info_layout.addWidget(self.sample_rate_label)
        audio_info_layout.addWidget(self.sample_rate)
        audio_info_layout.addWidget(self.buffer_size_label)
        audio_info_layout.addWidget(self.buffer_size)
        
        audio_layout.addLayout(audio_info_layout)
        
        # Apply audio settings button
        self.apply_audio_button = QPushButton("Apply Audio Settings")
        self.apply_audio_button.clicked.connect(self.apply_audio_settings)
        audio_layout.addWidget(self.apply_audio_button)
        
        audio_group.setLayout(audio_layout)
        layout.addWidget(audio_group)
        
        # MIDI Input Selection
        midi_group = QGroupBox("MIDI Input")
        midi_layout = QVBoxLayout()
        
        self.midi_devices_label = QLabel("MIDI Input Device:")
        self.midi_devices = QComboBox()
        
        # Get available MIDI inputs
        self.refresh_midi_devices()
        
        # Add refresh button
        self.refresh_midi_button = QPushButton("Refresh MIDI Devices")
        self.refresh_midi_button.clicked.connect(self.refresh_midi_devices)
        
        midi_layout.addWidget(self.midi_devices_label)
        midi_layout.addWidget(self.midi_devices)
        midi_layout.addWidget(self.refresh_midi_button)
        
        midi_group.setLayout(midi_layout)
        layout.addWidget(midi_group)
        
        # Add spacer to push controls to the top
        layout.addStretch()
        
        tab.setLayout(layout)
        return tab
    
    def refresh_midi_devices(self):
        """Refresh the list of MIDI devices"""
        # Store the currently selected device name if there is one
        current_device = None
        if self.midi_devices.count() > 0 and self.midi_devices.currentIndex() >= 0:
            current_device = self.midi_devices.currentText()
        
        # Clear and refresh the list
        self.midi_devices.clear()
        midi_inputs = mido.get_input_names()
        
        if midi_inputs:
            for name in midi_inputs:
                self.midi_devices.addItem(name)
            
            # Reconnect the signal after populating items to avoid triggering during setup
            try:
                self.midi_devices.currentIndexChanged.disconnect(self.change_midi_device)
            except:
                pass
            self.midi_devices.currentIndexChanged.connect(self.change_midi_device)
            
            # Try to reselect the previously selected device, or select the first one
            if current_device:
                index = self.midi_devices.findText(current_device)
                if index >= 0:
                    self.midi_devices.setCurrentIndex(index)
                    return
            
            # If we get here, either there was no previous device or it's no longer available
            # Select the first device
            self.change_midi_device(0)
        else:
            self.midi_devices.addItem("No MIDI devices detected")
    
    def change_midi_device(self, index):
        """Change the MIDI input device"""
        if index < 0:
            return
        
        # Get the selected device name directly from dropdown
        selected_device = self.midi_devices.currentText()
        
        # Only proceed if it's a valid device name (not a placeholder message)
        if selected_device in ["No MIDI devices detected", "Error listing MIDI devices"]:
            return
        
        # Open the selected device in the MIDI handler
        try:
            # Create a new MIDI handler to ensure clean state
            if hasattr(self, 'midi_handler'):
                # Disconnect old signals first
                try:
                    self.midi_handler.note_on_signal.disconnect()
                    self.midi_handler.note_off_signal.disconnect()
                    self.midi_handler.pitch_bend_signal.disconnect()
                except:
                    pass
                # Close the port
                self.midi_handler.close_port()
                
            # Create a fresh MIDI handler
            self.midi_handler = MidiHandler()
            
            # Reconnect signals
            self.connect_midi_to_particle()
            
            # Open the port
            success = self.midi_handler.open_port(selected_device)
            if success:
                print(f"Connected to MIDI device: {selected_device}")
            else:
                QMessageBox.warning(self, "MIDI Error", f"Could not connect to MIDI device: {selected_device}")
        except Exception as e:
            QMessageBox.warning(self, "MIDI Error", f"Error connecting to MIDI device: {e}")
            print(f"MIDI connection error details: {e}")
            # Try to reconnect to first available device
            self.refresh_midi_devices()
    
    def change_audio_device(self, index):
        """Store the selected audio device index to be applied with the button"""
        # Just store the selection - actual change happens when Apply is clicked
        pass
    
    def apply_audio_settings(self):
        """Apply audio settings (requires restart)"""
        if not self.server:
            return
        
        # Get the selected audio device
        if self.audio_devices.currentIndex() < 0:
            return
            
        device_index = self.audio_devices.itemData(self.audio_devices.currentIndex())
        if device_index is None:
            return
            
        sample_rate = int(self.sample_rate.currentText())
        buffer_size = int(self.buffer_size.currentText())
        
        # Warn that we need to restart the audio engine
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setText("Changing audio settings requires restarting the audio engine.")
        msg.setInformativeText("Any playing notes will be cut off. Continue?")
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        
        if msg.exec_() == QMessageBox.Cancel:
            return
        
        # Shutdown the current audio engine and components
        if hasattr(self, 'particle'):
            self.particle.shutdown()
        
        if self.server:
            self.server.stop()
            self.server.shutdown()
        
        # Restart with new settings
        try:
            # Initialize with new settings
            self.server = pyo.Server()
            
            # Try to set the output device
            try:
                print(f"Setting output device to index {device_index}")
                self.server.setOutputDevice(device_index)
            except Exception as e:
                print(f"Could not set output device: {e}")
                # Try alternative setting method with device number
                try:
                    print(f"Attempting to set output device using alternative method")
                    self.server = pyo.Server(sr=sample_rate, buffersize=buffer_size, 
                                            nchnls=2, ichnls=0, duplex=0, 
                                            audio='portaudio', jackname='pyo', 
                                            outdevice=device_index)
                except Exception as e2:
                    print(f"Alternative method also failed: {e2}")
            
            # Set sampling rate and buffer size
            try:
                self.server.setSamplingRate(sample_rate)
                self.server.setBufferSize(buffer_size)
            except Exception as e:
                print(f"Could not set sampling rate or buffer size: {e}")
            
            # Boot and start
            self.server.boot()
            self.server.start()
            
            # Reinitialize the particle
            self.particle = Particle(self.server)
            
            # Reconnect MIDI to particle
            self.connect_midi_to_particle()
            
            # Get the current settings for confirmation
            current_sr = self.server.getSamplingRate()
            current_bs = self.server.getBufferSize()
            
            QMessageBox.information(self, "Audio Settings", 
                f"Audio settings applied successfully.\nSample Rate: {current_sr} Hz\nBuffer Size: {current_bs} samples")
                
        except Exception as e:
            QMessageBox.critical(self, "Audio Error", 
                f"Error applying audio settings: {e}\n\nThe synthesizer may not produce sound.")
    
    def save_patch(self):
        """Save the current patch to file"""
        try:
            # Create a patch dictionary with parameters from both oscillators
            patch = {
                "op1": self._get_osc_params(self.op1_ui),
                "car1": self._get_osc_params(self.car1_ui)
            }
            
            # Use the settings module to save it
            save_patch(PATCH_FILE, patch)
            print(f"Patch saved to {PATCH_FILE}")
        except Exception as e:
            print(f"Error saving patch: {e}")
            
    def load_patch(self):
        """Load a patch from file"""
        try:
            # Load the patch data
            patch = load_patch(PATCH_FILE, None)
            if not patch:
                return
                
            # Apply to each oscillator UI
            if "op1" in patch:
                self._set_osc_params(self.op1_ui, patch["op1"])
                # Apply bypass states to the actual oscillator
                if "OP1" in self.particle.oscillators:
                    op1 = self.particle.oscillators["OP1"]
                    # Apply bypass states
                    if "bypass" in patch["op1"]:
                        for section, state in patch["op1"]["bypass"].items():
                            op1.set_bypass(section, state)
                    # Apply panner settings
                    if "pan_position" in patch["op1"]:
                        op1.set_pan_position(patch["op1"]["pan_position"])
                    if "stereo_width" in patch["op1"]:
                        op1.set_stereo_width(patch["op1"]["stereo_width"])
                    if "autopan_enabled" in patch["op1"]:
                        op1.set_autopan(patch["op1"]["autopan_enabled"],
                                        patch["op1"].get("autopan_rate", None))
                
            if "car1" in patch:
                self._set_osc_params(self.car1_ui, patch["car1"])
                # Apply bypass states to the actual oscillator
                if "CAR1" in self.particle.oscillators:
                    car1 = self.particle.oscillators["CAR1"]
                    # Apply bypass states
                    if "bypass" in patch["car1"]:
                        for section, state in patch["car1"]["bypass"].items():
                            car1.set_bypass(section, state)
                    # Apply panner settings
                    if "pan_position" in patch["car1"]:
                        car1.set_pan_position(patch["car1"]["pan_position"])
                    if "stereo_width" in patch["car1"]:
                        car1.set_stereo_width(patch["car1"]["stereo_width"])
                    if "autopan_enabled" in patch["car1"]:
                        car1.set_autopan(patch["car1"]["autopan_enabled"],
                                        patch["car1"].get("autopan_rate", None))
                
            print(f"Patch loaded from {PATCH_FILE}")
        except Exception as e:
            print(f"Error loading patch: {e}")
            
    def _get_osc_params(self, ui):
        """Extract parameters from an oscillator UI"""
        params = {}
        
        # Get bypass states
        params["bypass"] = {
            "osc": ui.bypass_state['osc'],
            "freq": ui.bypass_state['freq'],
            "amp": ui.bypass_state['amp'],
            "filter": ui.bypass_state['filter'],
            "delay": ui.bypass_state['delay']
        }
        
        # Extract all parameters from the UI
        params["wave_type"] = ui.wave_type.currentText()
        params["num_oscs"] = ui.num_oscs.itemAt(1).widget().value()
        params["detune"] = ui.detune.itemAt(1).widget().value()
        params["spread"] = ui.spread.itemAt(1).widget().value()
        params["detune_mode"] = ui.detune_mode.currentText()
        params["phase_spread"] = ui.phase_spread.itemAt(1).widget().value()
        params["amp_dist"] = ui.amp_dist.currentText()
        
        # Get modulation amount if present (for carriers only)
        if hasattr(ui, 'mod_amount'):
            params["mod_amount"] = ui.mod_amount.itemAt(1).widget().value()
        
        # Frequency parameters
        params["freq_mode"] = ui.freq_mode.currentText()
        params["manual_freq"] = ui.manual_freq.itemAt(1).widget().value()
        params["coarse_detune"] = ui.coarse_detune.itemAt(1).widget().value()
        params["fine_detune"] = ui.fine_detune.itemAt(1).widget().value()
        
        # Slew parameters
        params["slew_delay"] = ui.slew_delay.itemAt(1).widget().value()
        params["slew_time"] = ui.slew_time.itemAt(1).widget().value()
        params["start_rand"] = ui.start_rand.itemAt(1).widget().value()
        params["start_slew"] = ui.start_slew.itemAt(1).widget().value()
        params["end_slew"] = ui.end_slew.itemAt(1).widget().value()
        
        # Frequency envelope
        params["freq_env_depth"] = ui.freq_env_depth.itemAt(1).widget().value()
        params["freq_attack"] = ui.freq_attack.itemAt(1).widget().value()
        params["freq_decay"] = ui.freq_decay.itemAt(1).widget().value()
        params["freq_sustain"] = ui.freq_sustain.itemAt(1).widget().value()
        params["freq_release"] = ui.freq_release.itemAt(1).widget().value()
        
        # Amplitude parameters
        params["amp_ramp_delay"] = ui.amp_ramp_delay.itemAt(1).widget().value()
        params["amp_ramp_time"] = ui.amp_ramp_time.itemAt(1).widget().value()
        params["amp_ramp_start"] = ui.amp_ramp_start.itemAt(1).widget().value()
        params["amp_ramp_end"] = ui.amp_ramp_end.itemAt(1).widget().value()
        params["amp_attack"] = ui.amp_attack.itemAt(1).widget().value()
        params["amp_decay"] = ui.amp_decay.itemAt(1).widget().value()
        params["amp_sustain"] = ui.amp_sustain.itemAt(1).widget().value()
        params["amp_release"] = ui.amp_release.itemAt(1).widget().value()
        
        # Filter parameters
        params["filter_res"] = ui.filter_res.itemAt(1).widget().value()
        params["filter_ramp_delay"] = ui.filter_ramp_delay.itemAt(1).widget().value()
        params["filter_ramp_time"] = ui.filter_ramp_time.itemAt(1).widget().value()
        params["filter_ramp_start"] = ui.filter_ramp_start.itemAt(1).widget().value()
        params["filter_ramp_end"] = ui.filter_ramp_end.itemAt(1).widget().value()
        
        # Feedback
        params["feedback_source"] = ui.feedback_source.currentText()
        params["feedback_depth"] = ui.feedback_depth.itemAt(1).widget().value()
        
        # Delay parameters
        params["left_delays"] = [ui.left_delays[i].itemAt(1).widget().value() for i in range(3)]
        params["right_delays"] = [ui.right_delays[i].itemAt(1).widget().value() for i in range(3)]
        params["left_feedback"] = ui.left_feedback.itemAt(1).widget().value()
        params["right_feedback"] = ui.right_feedback.itemAt(1).widget().value()
        
        # Panner parameters
        params["pan_position"] = ui.pan_position.itemAt(1).widget().value()
        params["stereo_width"] = ui.stereo_width.itemAt(1).widget().value()
        params["autopan_enabled"] = ui.autopan_checkbox.isChecked()
        params["autopan_rate"] = ui.autopan_rate.itemAt(1).widget().value()
        
        return params
    
    def _set_osc_params(self, ui, params):
        """Apply parameters to an oscillator UI"""
        if not params:
            return
            
        # Set bypass states if available
        if "bypass" in params:
            for section, state in params["bypass"].items():
                ui.set_bypass_state(section, state)
            
        # Apply all parameters to the UI
        if "wave_type" in params:
            index = ui.wave_type.findText(params["wave_type"])
            if index >= 0:
                ui.wave_type.setCurrentIndex(index)
        
        # Set modulation amount if present (for carriers only)
        if hasattr(ui, 'mod_amount') and "mod_amount" in params:
            self._set_value(ui.mod_amount, params.get("mod_amount"))
                
        self._set_value(ui.num_oscs, params.get("num_oscs"))
        self._set_value(ui.detune, params.get("detune"))
        self._set_value(ui.spread, params.get("spread"))
        
        if "detune_mode" in params:
            index = ui.detune_mode.findText(params["detune_mode"])
            if index >= 0:
                ui.detune_mode.setCurrentIndex(index)
                
        self._set_value(ui.phase_spread, params.get("phase_spread"))
        
        if "amp_dist" in params:
            index = ui.amp_dist.findText(params["amp_dist"])
            if index >= 0:
                ui.amp_dist.setCurrentIndex(index)
                
        # Frequency parameters
        if "freq_mode" in params:
            index = ui.freq_mode.findText(params["freq_mode"])
            if index >= 0:
                ui.freq_mode.setCurrentIndex(index)
                
        self._set_value(ui.manual_freq, params.get("manual_freq"))
        self._set_value(ui.coarse_detune, params.get("coarse_detune"))
        self._set_value(ui.fine_detune, params.get("fine_detune"))
        
        # Slew parameters
        self._set_value(ui.slew_delay, params.get("slew_delay"))
        self._set_value(ui.slew_time, params.get("slew_time"))
        self._set_value(ui.start_rand, params.get("start_rand"))
        self._set_value(ui.start_slew, params.get("start_slew"))
        self._set_value(ui.end_slew, params.get("end_slew"))
        
        # Frequency envelope
        self._set_value(ui.freq_env_depth, params.get("freq_env_depth"))
        self._set_value(ui.freq_attack, params.get("freq_attack"))
        self._set_value(ui.freq_decay, params.get("freq_decay"))
        self._set_value(ui.freq_sustain, params.get("freq_sustain"))
        self._set_value(ui.freq_release, params.get("freq_release"))
        
        # Amplitude parameters
        self._set_value(ui.amp_ramp_delay, params.get("amp_ramp_delay"))
        self._set_value(ui.amp_ramp_time, params.get("amp_ramp_time"))
        self._set_value(ui.amp_ramp_start, params.get("amp_ramp_start"))
        self._set_value(ui.amp_ramp_end, params.get("amp_ramp_end"))
        self._set_value(ui.amp_attack, params.get("amp_attack"))
        self._set_value(ui.amp_decay, params.get("amp_decay"))
        self._set_value(ui.amp_sustain, params.get("amp_sustain"))
        self._set_value(ui.amp_release, params.get("amp_release"))
        
        # Filter parameters
        self._set_value(ui.filter_res, params.get("filter_res"))
        self._set_value(ui.filter_ramp_delay, params.get("filter_ramp_delay"))
        self._set_value(ui.filter_ramp_time, params.get("filter_ramp_time"))
        self._set_value(ui.filter_ramp_start, params.get("filter_ramp_start"))
        self._set_value(ui.filter_ramp_end, params.get("filter_ramp_end"))
        
        # Feedback
        if "feedback_source" in params:
            index = ui.feedback_source.findText(params["feedback_source"])
            if index >= 0:
                ui.feedback_source.setCurrentIndex(index)
                
        self._set_value(ui.feedback_depth, params.get("feedback_depth"))
        
        # Delay parameters
        if "left_delays" in params and len(params["left_delays"]) == 3:
            for i in range(3):
                self._set_value(ui.left_delays[i], params["left_delays"][i])
                
        if "right_delays" in params and len(params["right_delays"]) == 3:
            for i in range(3):
                self._set_value(ui.right_delays[i], params["right_delays"][i])
                
        self._set_value(ui.left_feedback, params.get("left_feedback"))
        self._set_value(ui.right_feedback, params.get("right_feedback"))
        
        # Set panner parameters
        self._set_value(ui.pan_position, params.get("pan_position"))
        self._set_value(ui.stereo_width, params.get("stereo_width"))
        if "autopan_enabled" in params:
            ui.autopan_checkbox.setChecked(params["autopan_enabled"])
        self._set_value(ui.autopan_rate, params.get("autopan_rate"))
    
    def _set_value(self, slider_layout, value):
        """Helper to set a value in a slider layout"""
        if value is not None and slider_layout is not None:
            try:
                slider_layout.itemAt(1).widget().setValue(value)
            except Exception as e:
                print(f"Error setting value: {e}")
    
    def save_on_exit(self):
        """Save patch on exit and clean up resources"""
        # Save the current patch
        self.save_patch()
        
        # Close MIDI handler
        if hasattr(self, 'midi_handler'):
            self.midi_handler.close_port()
        
        # Shut down the particle
        if hasattr(self, 'particle'):
            self.particle.shutdown()
        
        # Stop audio server
        if self.server:
            self.server.stop()
            self.server.shutdown()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
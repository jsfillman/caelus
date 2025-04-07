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

from synth_ui_updated import SynthUI
from wavetables import WaveformBank
from settings import load_patch, save_patch
from audio_engine import AudioEngine
from midi_handler import MidiHandler

# Default patch file
PATCH_FILE = "last_patch.yaml"

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Caelux Mini")
        
        # Initialize audio server
        self.server = None
        self.init_audio_server()
        
        # Initialize the audio engine
        self.audio_engine = AudioEngine(self.server)
        
        # Initialize the MIDI handler
        self.midi_handler = MidiHandler()
        
        # Connect MIDI signals to audio engine
        self.connect_midi_to_audio()
        
        # Create main layout
        main_layout = QHBoxLayout()
        
        # Create tab widget for vertical tabs
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.West)  # Put tabs on the left side
        
        # Add Global tab
        global_tab = self.create_global_tab()
        self.tabs.addTab(global_tab, "G")
        self.tabs.setTabToolTip(0, "Global Settings")
        
        # Add Carrier tab (synth UI)
        self.synth_ui = SynthUI(self.server)
        self.tabs.addTab(self.synth_ui, "C1")
        self.tabs.setTabToolTip(1, "Carrier 1")
        
        main_layout.addWidget(self.tabs)
        self.setLayout(main_layout)
        
        # Set the window size
        self.setMinimumWidth(1300)
        self.setMinimumHeight(800)
        
        # Load the last patch if available
        load_patch(PATCH_FILE, self.synth_ui)
        
        # Register function to save patch on exit
        atexit.register(self.save_on_exit)
    
    def connect_midi_to_audio(self):
        """Connect MIDI handler signals to audio engine methods"""
        if not hasattr(self, 'midi_handler') or not hasattr(self, 'audio_engine'):
            return
            
        # Connect note signals
        self.midi_handler.note_on_signal.connect(self.handle_note_on)
        self.midi_handler.note_off_signal.connect(self.audio_engine.note_off)
        
        # Connect other MIDI signals
        self.midi_handler.pitch_bend_signal.connect(self.audio_engine.pitch_bend)
        self.midi_handler.aftertouch_signal.connect(self.audio_engine.aftertouch)
        
        # Connect CC signals - handle sustain specifically
        self.midi_handler.cc_signal.connect(self.handle_cc)
    
    def handle_note_on(self, note, velocity):
        """Handle note on by passing current synth parameters"""
        self.audio_engine.note_on(note, velocity, self.synth_ui)
    
    def handle_cc(self, control, value):
        """Handle MIDI CC messages"""
        # Special case for sustain pedal
        if control == 64:
            self.audio_engine.sustain_pedal(value)
    
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
        
        # Get the list of available devices
        midi_inputs = mido.get_input_names()
        if not midi_inputs or index >= len(midi_inputs):
            return
        
        # Open the selected device in the MIDI handler
        try:
            success = self.midi_handler.open_port(midi_inputs[index])
            if success:
                print(f"Connected to MIDI device: {midi_inputs[index]}")
            else:
                QMessageBox.warning(self, "MIDI Error", f"Could not connect to MIDI device: {midi_inputs[index]}")
        except Exception as e:
            QMessageBox.warning(self, "MIDI Error", f"Error connecting to MIDI device: {e}")
    
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
        
        # Determine if any settings have changed - assume they have since we can't easily check
        
        # Warn that we need to restart the audio engine
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setText("Changing audio settings requires restarting the audio engine.")
        msg.setInformativeText("Any playing notes will be cut off. Continue?")
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        
        if msg.exec_() == QMessageBox.Cancel:
            return
        
        # Shutdown the current audio engine and components
        if hasattr(self, 'audio_engine'):
            self.audio_engine.shutdown()
        
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
            
            # Reinitialize the audio engine
            self.audio_engine = AudioEngine(self.server)
            
            # Reconnect MIDI to audio
            self.connect_midi_to_audio()
            
            # Get the current settings for confirmation
            current_sr = self.server.getSamplingRate()
            current_bs = self.server.getBufferSize()
            
            QMessageBox.information(self, "Audio Settings", 
                f"Audio settings applied successfully.\nSample Rate: {current_sr} Hz\nBuffer Size: {current_bs} samples")
                
        except Exception as e:
            QMessageBox.critical(self, "Audio Error", 
                f"Error applying audio settings: {e}\n\nThe synthesizer may not produce sound.")
    
    def get_current_device_info(self):
        """Get information about the current audio output device"""
        try:
            if not self.server:
                return None
                
            # Try different methods to get the current device
            methods = ["getOutputDevice", "getDefaultOutputDevice", "getDefaultOutput"]
            device_index = None
            
            for method in methods:
                try:
                    if hasattr(self.server, method):
                        device_index = getattr(self.server, method)()
                        print(f"Got device index {device_index} using {method}")
                        break
                except Exception as e:
                    print(f"Method {method} failed: {e}")
            
            if device_index is None:
                print("Could not determine current output device index")
                return None
                
            # Get device info from the index
            audio_info = pyo.pa_get_devices_infos()
            if device_index < len(audio_info):
                return audio_info[device_index]
            else:
                return None
                
        except Exception as e:
            print(f"Error getting device info: {e}")
            return None
            
    def save_on_exit(self):
        """Save patch on exit and clean up resources"""
        # Save the current patch
        save_patch(PATCH_FILE, self.synth_ui)
        
        # Close MIDI handler
        if hasattr(self, 'midi_handler'):
            self.midi_handler.close_port()
        
        # Shut down the audio engine
        if hasattr(self, 'audio_engine'):
            self.audio_engine.shutdown()
        
        # Stop audio server
        if self.server:
            self.server.stop()
            self.server.shutdown()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())

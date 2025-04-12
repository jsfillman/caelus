#!/usr/bin/env python3
"""
Audio configuration utility for Caelux Mini
This utility allows direct selection of audio devices before launching the main application,
helping to resolve audio device selection issues.
"""

import os
import sys
import pyo
import yaml
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QComboBox, QLabel, QPushButton, QGroupBox, QSpinBox, QMessageBox
)
from PyQt5.QtCore import Qt

class AudioSetupWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Caelux Mini - Audio Setup")
        self.resize(600, 400)
        
        # Create main widget and layout
        central_widget = QWidget()
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        
        # Create a container for device selection
        device_group = QGroupBox("Audio Device Selection")
        device_layout = QVBoxLayout()
        
        # Device selection dropdown
        self.devices_label = QLabel("Select Audio Output Device:")
        self.devices_combo = QComboBox()
        self.devices_combo.setMinimumWidth(400)
        
        # Load available devices
        self.load_audio_devices()
        
        # Device info label
        self.device_info = QLabel("Device info: Not selected")
        self.device_info.setWordWrap(True)
        
        # Connect signal for device selection
        self.devices_combo.currentIndexChanged.connect(self.update_device_info)
        
        # Add to layout
        device_layout.addWidget(self.devices_label)
        device_layout.addWidget(self.devices_combo)
        device_layout.addWidget(self.device_info)
        device_group.setLayout(device_layout)
        main_layout.addWidget(device_group)
        
        # Audio parameters
        params_group = QGroupBox("Audio Parameters")
        params_layout = QVBoxLayout()
        
        # Sample rate
        sr_layout = QHBoxLayout()
        sr_label = QLabel("Sample Rate:")
        self.sr_combo = QComboBox()
        self.sr_combo.addItems(["44100", "48000", "96000"])
        self.sr_combo.setCurrentText("44100")
        sr_layout.addWidget(sr_label)
        sr_layout.addWidget(self.sr_combo)
        
        # Buffer size
        bs_layout = QHBoxLayout()
        bs_label = QLabel("Buffer Size:")
        self.bs_combo = QComboBox()
        self.bs_combo.addItems(["64", "128", "256", "512", "1024", "2048"])
        self.bs_combo.setCurrentText("256")
        bs_layout.addWidget(bs_label)
        bs_layout.addWidget(self.bs_combo)
        
        # Channel count
        channels_layout = QHBoxLayout()
        channels_label = QLabel("Number of Channels:")
        self.channels_spin = QSpinBox()
        self.channels_spin.setMinimum(2)
        self.channels_spin.setMaximum(8)
        self.channels_spin.setValue(2)
        self.channels_spin.setSingleStep(2)
        channels_layout.addWidget(channels_label)
        channels_layout.addWidget(self.channels_spin)
        
        # Add parameters to layout
        params_layout.addLayout(sr_layout)
        params_layout.addLayout(bs_layout)
        params_layout.addLayout(channels_layout)
        params_group.setLayout(params_layout)
        main_layout.addWidget(params_group)
        
        # Test button
        self.test_button = QPushButton("Test Selected Device")
        self.test_button.clicked.connect(self.test_audio_device)
        main_layout.addWidget(self.test_button)
        
        # Apply button
        self.apply_button = QPushButton("Save Settings and Launch Caelux Mini")
        self.apply_button.clicked.connect(self.save_and_launch)
        main_layout.addWidget(self.apply_button)
        
        # Load any existing settings
        self.load_existing_settings()
    
    def load_audio_devices(self):
        """Load available audio devices"""
        try:
            # Clear existing items
            self.devices_combo.clear()
            
            # Try to get devices
            try:
                # Try the newer API first
                devices = pyo.pa_get_output_devices()
                print(f"Devices: {devices}")
                
                if isinstance(devices, dict):
                    # Dictionary format (index -> name)
                    for idx, name in sorted(devices.items()):
                        self.devices_combo.addItem(name, idx)
                elif isinstance(devices, (list, tuple)):
                    # List format or ([names], [indices]) format
                    if len(devices) == 2 and isinstance(devices[0], list) and isinstance(devices[1], list):
                        # ([names], [indices]) format
                        names = devices[0]
                        indices = devices[1]
                        for i, name in enumerate(names):
                            if i < len(indices):
                                self.devices_combo.addItem(name, indices[i])
                    else:
                        # Standard list format
                        for i, name in enumerate(devices):
                            if name:  # Skip empty entries
                                self.devices_combo.addItem(name, i)
            except:
                # Try the older API
                audio_info = pyo.pa_get_devices_infos()
                for i, dev in enumerate(audio_info):
                    try:
                        if isinstance(dev, dict) and 'name' in dev:
                            name = dev['name']
                            self.devices_combo.addItem(name, i)
                        # Handle nested dict format
                        else:
                            for key, value in dev.items():
                                if isinstance(value, dict) and 'name' in value:
                                    name = value['name']
                                    idx = int(key) if key.isdigit() else i
                                    self.devices_combo.addItem(name, idx)
                    except:
                        pass
            
            # If we still have no devices, add a dummy entry
            if self.devices_combo.count() == 0:
                self.devices_combo.addItem("No audio devices detected", -1)
                
        except Exception as e:
            self.devices_combo.addItem(f"Error listing devices: {e}", -1)
    
    def load_existing_settings(self):
        """Load existing audio settings if available"""
        audio_settings_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio_settings.yaml")
        
        if os.path.exists(audio_settings_file):
            try:
                with open(audio_settings_file, 'r') as f:
                    settings = yaml.safe_load(f)
                
                # Apply settings to UI
                if settings:
                    # Set device if found
                    if 'device_index' in settings:
                        # Find the device in our combo box
                        for i in range(self.devices_combo.count()):
                            if self.devices_combo.itemData(i) == settings['device_index']:
                                self.devices_combo.setCurrentIndex(i)
                                break
                    
                    # Set sample rate
                    if 'sample_rate' in settings:
                        self.sr_combo.setCurrentText(str(settings['sample_rate']))
                    
                    # Set buffer size
                    if 'buffer_size' in settings:
                        self.bs_combo.setCurrentText(str(settings['buffer_size']))
                    
                    # Set channel count
                    if 'num_channels' in settings:
                        self.channels_spin.setValue(settings['num_channels'])
            except Exception as e:
                print(f"Error loading settings: {e}")
    
    def update_device_info(self, index):
        """Update the device info when selection changes"""
        if index < 0:
            return
        
        device_name = self.devices_combo.currentText()
        device_index = self.devices_combo.currentData()
        
        # Try to get additional device info
        device_info = f"Selected Device: {device_name} (Index: {device_index})"
        
        # Try to match with multichannel devices
        if any(term in device_name.lower() for term in ["quad", "surround", "5.1", "7.1", "8", "loopback audio 2"]):
            device_info += "\nThis appears to be a multichannel device (4+ channels)."
            # Suggest more channels
            self.channels_spin.setValue(4)
        
        self.device_info.setText(device_info)
    
    def test_audio_device(self):
        """Test the selected audio device"""
        if self.devices_combo.currentData() == -1:
            QMessageBox.warning(self, "Error", "No valid device selected")
            return
        
        device_index = self.devices_combo.currentData()
        device_name = self.devices_combo.currentText()
        sr = int(self.sr_combo.currentText())
        bs = int(self.bs_combo.currentText())
        nchnls = self.channels_spin.value()
        
        self.test_button.setEnabled(False)
        self.test_button.setText("Testing... (listen for tones)")
        QApplication.processEvents()
        
        try:
            # Create a test server
            s = pyo.Server(sr=sr, buffersize=bs, nchnls=nchnls)
            s.boot()
            s.setOutputDevice(device_index)
            s.start()
            
            # Test each channel
            for channel in range(nchnls):
                # Create a sine oscillator for this channel
                freq = 440 * (1 + channel * 0.25)  # Different frequency for each channel
                sine = pyo.Sine(freq=freq, mul=0.3)
                
                # Create a mixer to route to the correct channel
                mixer = pyo.Mixer(voices=1, chnls=nchnls)
                mixer.addInput(0, sine)
                mixer.setAmp(0, channel, 1.0)  # Route to the current channel
                mixer.out()
                
                # Let it play briefly
                QApplication.processEvents()
                pyo.time.sleep(0.5)
                
                # Clean up
                sine.stop()
                mixer.stop()
            
            # Clean up
            s.stop()
            s.shutdown()
            
            QMessageBox.information(self, "Test Complete", 
                f"Device {device_name} test complete.\n\n"
                f"You should have heard {nchnls} short tones of different pitches, "
                f"one for each audio channel.")
            
        except Exception as e:
            QMessageBox.critical(self, "Test Failed", 
                f"Could not test device {device_name}:\n\n{e}")
        
        self.test_button.setEnabled(True)
        self.test_button.setText("Test Selected Device")
    
    def save_and_launch(self):
        """Save settings and launch the main application"""
        if self.devices_combo.currentData() == -1:
            QMessageBox.warning(self, "Error", "No valid device selected")
            return
        
        device_index = self.devices_combo.currentData()
        device_name = self.devices_combo.currentText()
        sr = int(self.sr_combo.currentText())
        bs = int(self.bs_combo.currentText())
        nchnls = self.channels_spin.value()
        
        # Save settings
        try:
            # Create the settings file path
            audio_settings_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio_settings.yaml")
            
            # Create settings dictionary
            settings = {
                'device_index': device_index,
                'device_name': device_name,
                'sample_rate': sr,
                'buffer_size': bs,
                'num_channels': nchnls
            }
            
            # Save to file
            with open(audio_settings_file, 'w') as f:
                yaml.dump(settings, f)
            
            # Show success message
            launch = QMessageBox.question(self, "Settings Saved", 
                f"Audio settings saved successfully:\n\n"
                f"Device: {device_name}\n"
                f"Sample Rate: {sr} Hz\n"
                f"Buffer Size: {bs}\n"
                f"Channels: {nchnls}\n\n"
                f"Launch Caelux Mini now?", 
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            
            if launch == QMessageBox.Yes:
                # Launch the main application
                script_dir = os.path.dirname(os.path.abspath(__file__))
                main_script = os.path.join(script_dir, "main_updated.py")
                
                if os.path.exists(main_script):
                    # Close this window first
                    self.close()
                    
                    # Create a command to execute the main script
                    import subprocess
                    subprocess.Popen([sys.executable, main_script])
                else:
                    QMessageBox.warning(self, "Launch Failed", 
                        f"Could not find main application script at {main_script}")
        
        except Exception as e:
            QMessageBox.critical(self, "Save Failed", 
                f"Could not save audio settings:\n\n{e}")

def main():
    """Main entry point"""
    app = QApplication(sys.argv)
    window = AudioSetupWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
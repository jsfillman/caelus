#!/usr/bin/env python3
"""
Quad Channel Mapper Tool
Tests each channel individually and allows remapping of output channels
"""

import pyo
import time
import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QGroupBox, QSlider, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer

class ChannelMapper(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Quad Channel Mapper")
        self.resize(600, 400)
        
        # Initialize audio server with 4 channels
        self.server = None
        self.init_audio_server()
        
        # Create main layout
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        
        # Info label
        info_label = QLabel("This tool helps identify and test quad channel mapping problems.")
        info_label.setWordWrap(True)
        main_layout.addWidget(info_label)
        
        # Server status
        status_label = QLabel("Server Status:")
        self.server_status = QLabel("Not initialized")
        if self.server and self.server.getIsStarted():
            self.server_status.setText(f"Running - {self.server.getNchnls()} channels")
        
        status_layout = QHBoxLayout()
        status_layout.addWidget(status_label)
        status_layout.addWidget(self.server_status)
        main_layout.addLayout(status_layout)
        
        # Create channel test buttons
        test_group = QGroupBox("Channel Tests")
        test_layout = QVBoxLayout()
        test_group.setLayout(test_layout)
        
        # Test all channels
        test_all_button = QPushButton("Test All Channels Sequentially")
        test_all_button.clicked.connect(self.test_all_channels)
        test_layout.addWidget(test_all_button)
        
        # Individual channel sliders and test buttons
        self.channel_sliders = []
        
        channel_names = ["Front Left (0)", "Front Right (1)", "Rear Left (2)", "Rear Right (3)"]
        
        for i, name in enumerate(channel_names):
            channel_layout = QHBoxLayout()
            
            # Create slider for this channel
            slider = QSlider(Qt.Horizontal)
            slider.setMinimum(0)
            slider.setMaximum(100)
            slider.setValue(0)
            slider.setTracking(True)
            slider.valueChanged.connect(lambda value, ch=i: self.slider_changed(ch, value))
            
            # Store the slider
            self.channel_sliders.append(slider)
            
            # Create container for this channel's controls
            ch_label = QLabel(name)
            ch_label.setMinimumWidth(100)
            test_button = QPushButton("Test")
            test_button.clicked.connect(lambda checked, ch=i: self.test_channel(ch))
            
            channel_layout.addWidget(ch_label)
            channel_layout.addWidget(slider)
            channel_layout.addWidget(test_button)
            
            test_layout.addLayout(channel_layout)
        
        main_layout.addWidget(test_group)
        
        # Sinewaves for each channel
        self.sines = []
        self.channel_volumes = [0, 0, 0, 0]  # Volume for each channel 0-1.0
        
        for i in range(4):
            freq = 440 * (1 + i * 0.25)  # Different frequency for each channel
            sine = pyo.Sine(freq=freq, mul=0)
            mixer = pyo.Mixer(voices=1, chnls=4)
            mixer.addInput(0, sine)
            mixer.setAmp(0, i, 1.0)  # Route to the correct channel
            mixer.out()
            self.sines.append((sine, mixer))
        
        # Channel mapper (experimental)
        remap_group = QGroupBox("Channel Remapping (Experimental)")
        remap_layout = QVBoxLayout()
        remap_group.setLayout(remap_layout)
        
        # Create dropdown selectors for channel remapping
        self.channel_maps = []
        
        for i, name in enumerate(channel_names):
            map_layout = QHBoxLayout()
            map_label = QLabel(f"Map {name} to:")
            
            map_combo = QComboBox()
            for j in range(8):  # Support up to 8 channels
                map_combo.addItem(f"Channel {j}")
            map_combo.setCurrentIndex(i)  # Default to same channel
            
            self.channel_maps.append(map_combo)
            
            map_layout.addWidget(map_label)
            map_layout.addWidget(map_combo)
            
            remap_layout.addLayout(map_layout)
        
        # Apply mapping button
        apply_map_button = QPushButton("Apply Channel Mapping")
        apply_map_button.clicked.connect(self.apply_mapping)
        remap_layout.addWidget(apply_map_button)
        
        main_layout.addWidget(remap_group)
        
        # Create tone generator
        generator_group = QGroupBox("Continuous Tone Generator")
        generator_layout = QVBoxLayout()
        generator_group.setLayout(generator_layout)
        
        # Channel selection
        gen_layout = QHBoxLayout()
        gen_label = QLabel("Channel:")
        self.gen_channel = QSpinBox()
        self.gen_channel.setMinimum(0)
        self.gen_channel.setMaximum(7)  # Support up to 8 channels
        self.gen_channel.setValue(0)
        
        gen_start = QPushButton("Start")
        gen_start.clicked.connect(self.start_generator)
        gen_stop = QPushButton("Stop")
        gen_stop.clicked.connect(self.stop_generator)
        
        gen_layout.addWidget(gen_label)
        gen_layout.addWidget(self.gen_channel)
        gen_layout.addWidget(gen_start)
        gen_layout.addWidget(gen_stop)
        
        generator_layout.addLayout(gen_layout)
        
        main_layout.addWidget(generator_group)
        
        # Generator variable
        self.generator = None
    
    def init_audio_server(self):
        """Initialize audio server"""
        try:
            # Create server with 4 channels
            self.server = pyo.Server(nchnls=4)
            self.server.boot()
            self.server.start()
            
            # Print info
            print(f"Server initialized with {self.server.getNchnls()} channels")
        except Exception as e:
            print(f"Error initializing server: {e}")
            self.server = None
    
    def test_all_channels(self):
        """Test all channels sequentially"""
        if not self.server or not self.server.getIsStarted():
            QMessageBox.warning(self, "Error", "Audio server not running.")
            return
        
        # Create a message box to show during the test
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Channel Test")
        msg_box.setText("Testing channels...")
        msg_box.setStandardButtons(QMessageBox.NoButton)
        msg_box.show()
        
        # Reset all sliders
        for slider in self.channel_sliders:
            slider.setValue(0)
        
        # Get the number of channels
        try:
            num_channels = self.server.getNchnls()
        except:
            num_channels = 4
        
        # Test channels sequentially
        channel_duration = 1.0  # seconds per channel
        
        # Start with channel 0
        current_channel = [0]
        
        def test_next_channel():
            channel = current_channel[0]
            
            # If we've tested all channels, clean up and close dialog
            if channel >= num_channels:
                msg_box.setText("Channel Test Complete")
                msg_box.setStandardButtons(QMessageBox.Ok)
                return
            
            # Update message box
            channel_names = ["Front Left", "Front Right", "Rear Left", "Rear Right"]
            channel_name = channel_names[channel] if channel < len(channel_names) else f"Channel {channel}"
            msg_box.setText(f"Testing {channel_name} (Channel {channel})")
            
            # Animate the slider
            self.channel_sliders[channel].setValue(100)
            
            # Test this channel
            self.test_channel(channel)
            
            # Schedule moving to next channel
            QTimer.singleShot(int(channel_duration * 1000), lambda: 
                [self.channel_sliders[channel].setValue(0), 
                 current_channel.__setitem__(0, current_channel[0] + 1),
                 test_next_channel()])
        
        # Start the test
        test_next_channel()
    
    def test_channel(self, channel):
        """Test a specific channel"""
        if not self.server or not self.server.getIsStarted():
            return
        
        # Get the number of channels
        try:
            num_channels = self.server.getNchnls()
        except:
            num_channels = 4
        
        # Check channel is valid
        if channel >= num_channels:
            QMessageBox.warning(self, "Error", f"Channel {channel} not available.")
            return
        
        # Generate a tone on this channel for 0.5 seconds
        freq = 440 * (1 + channel * 0.25)  # Different frequency for each channel
        
        # Create a temporary tone generator
        temp_sine = pyo.Sine(freq=freq, mul=0.3)
        temp_out = pyo.Mix(temp_sine, voices=1)
        temp_out.out(chnl=channel)
        
        # Schedule cleanup
        QTimer.singleShot(500, lambda: [temp_sine.stop(), temp_out.stop()])
    
    def slider_changed(self, channel, value):
        """Handle slider changes"""
        # Convert to 0-1 range
        volume = value / 100.0
        
        # Update the volume
        self.channel_volumes[channel] = volume
        
        # Update the sine generator
        if channel < len(self.sines):
            sine, mixer = self.sines[channel]
            sine.mul = volume
    
    def apply_mapping(self):
        """Apply channel remapping"""
        mapping = [combo.currentIndex() for combo in self.channel_maps]
        
        # Recreate the sine generators with the new mapping
        for sine, mixer in self.sines:
            sine.stop()
            mixer.stop()
        
        self.sines = []
        
        for i in range(4):
            # Get the mapped channel
            mapped_channel = mapping[i]
            
            freq = 440 * (1 + i * 0.25)  # Different frequency for each channel
            sine = pyo.Sine(freq=freq, mul=self.channel_volumes[i])
            mixer = pyo.Mixer(voices=1, chnls=8)  # Support up to 8 channels
            mixer.addInput(0, sine)
            mixer.setAmp(0, mapped_channel, 1.0)  # Route to the mapped channel
            mixer.out()
            self.sines.append((sine, mixer))
        
        QMessageBox.information(self, "Mapping Applied", 
            f"Channel mapping applied:\n" +
            f"Channel 0 → {mapping[0]}\n" +
            f"Channel 1 → {mapping[1]}\n" +
            f"Channel 2 → {mapping[2]}\n" +
            f"Channel 3 → {mapping[3]}")
    
    def start_generator(self):
        """Start the tone generator on the selected channel"""
        if not self.server or not self.server.getIsStarted():
            QMessageBox.warning(self, "Error", "Audio server not running.")
            return
        
        # Stop any existing generator
        self.stop_generator()
        
        # Get the channel
        channel = self.gen_channel.value()
        
        # Create a new generator
        freq = 440 * (1 + channel * 0.25)  # Different frequency for each channel
        self.generator = (
            pyo.Sine(freq=freq, mul=0.3),  # The oscillator
            pyo.Mix(voices=1, chnls=8)      # The mixer
        )
        
        # Connect and route to the selected channel
        sine, mixer = self.generator
        mixer.addInput(0, sine)
        mixer.setAmp(0, channel, 1.0)
        mixer.out()
        
        QMessageBox.information(self, "Generator Started", 
            f"Tone generator started on channel {channel}.\n\nClick Stop when done.")
    
    def stop_generator(self):
        """Stop the tone generator"""
        if self.generator:
            sine, mixer = self.generator
            sine.stop()
            mixer.stop()
            self.generator = None

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ChannelMapper()
    window.show()
    sys.exit(app.exec_())
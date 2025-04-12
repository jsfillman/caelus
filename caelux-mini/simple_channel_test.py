#!/usr/bin/env python3
"""
Simple Channel Test Tool for Quad Audio
"""

import pyo
import time
import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QGroupBox
)
from PyQt5.QtCore import Qt, QTimer

class SimpleChannelTest(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simple Channel Test")
        self.resize(400, 300)
        
        # Initialize audio server with 4 channels
        self.server = None
        self.init_audio_server()
        
        # Create main layout
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        
        # Server status
        status_group = QGroupBox("Server Status")
        status_layout = QVBoxLayout()
        
        self.status_label = QLabel("Server not initialized")
        if self.server:
            channels = 0
            try:
                channels = self.server.getNchnls()
            except:
                pass
            self.status_label.setText(f"Server running with {channels} channels")
        
        status_layout.addWidget(self.status_label)
        status_group.setLayout(status_layout)
        main_layout.addWidget(status_group)
        
        # Channel test buttons
        test_group = QGroupBox("Channel Tests")
        test_layout = QVBoxLayout()
        
        # Channel names
        channel_names = ["Front Left (0)", "Front Right (1)", "Rear Left (2)", "Rear Right (3)"]
        
        # Test all button
        all_button = QPushButton("Test All Channels (Sequential)")
        all_button.clicked.connect(self.test_all_channels)
        test_layout.addWidget(all_button)
        
        # Individual channel buttons
        self.channel_buttons = []
        for i, name in enumerate(channel_names):
            button = QPushButton(f"Test {name}")
            button.clicked.connect(lambda checked, ch=i: self.test_channel(ch))
            test_layout.addWidget(button)
            self.channel_buttons.append(button)
        
        test_group.setLayout(test_layout)
        main_layout.addWidget(test_group)
        
        # Continuous tone controls
        tone_group = QGroupBox("Continuous Tone")
        tone_layout = QHBoxLayout()
        
        tone_label = QLabel("Channel:")
        self.tone_channel = QSpinBox()
        self.tone_channel.setMinimum(0)
        self.tone_channel.setMaximum(7)
        self.tone_channel.setValue(0)
        
        self.tone_start = QPushButton("Start")
        self.tone_start.clicked.connect(self.start_tone)
        self.tone_stop = QPushButton("Stop")
        self.tone_stop.clicked.connect(self.stop_tone)
        
        tone_layout.addWidget(tone_label)
        tone_layout.addWidget(self.tone_channel)
        tone_layout.addWidget(self.tone_start)
        tone_layout.addWidget(self.tone_stop)
        
        tone_group.setLayout(tone_layout)
        main_layout.addWidget(tone_group)
        
        # Store the tone generator
        self.tone_gen = None
    
    def init_audio_server(self):
        """Initialize the audio server"""
        try:
            self.server = pyo.Server(nchnls=4)
            self.server.boot()
            self.server.start()
            print(f"Server initialized")
        except Exception as e:
            print(f"Error initializing server: {e}")
            self.server = None
    
    def test_channel(self, channel):
        """Test a specific channel with a sine tone"""
        if not self.server:
            return
        
        # Disable the button temporarily
        self.channel_buttons[channel].setEnabled(False)
        
        # Create frequency based on channel (for identification)
        freq = 440 * (1 + channel * 0.25)  # A4, C#5, E5, G5
        
        # Create the sine oscillator
        sine = pyo.Sine(freq=freq, mul=0.3)
        
        # Direct output to the specific channel
        output = pyo.Mix(sine)
        output.out(chnl=channel)
        
        # Schedule stopping after 1 second
        QTimer.singleShot(1000, lambda: [sine.stop(), output.stop(), 
                                            self.channel_buttons[channel].setEnabled(True)])
    
    def test_all_channels(self):
        """Test all channels one after another"""
        if not self.server:
            return
        
        # Disable all buttons
        for button in self.channel_buttons:
            button.setEnabled(False)
        
        # Test duration
        duration = 1000  # ms
        
        # Test each channel sequentially
        for i in range(len(self.channel_buttons)):
            # Schedule each channel test with increasing delay
            QTimer.singleShot(i * duration, lambda ch=i: self.test_channel(ch))
        
        # Re-enable buttons after all tests complete
        QTimer.singleShot(len(self.channel_buttons) * duration, 
                          lambda: [button.setEnabled(True) for button in self.channel_buttons])
    
    def start_tone(self):
        """Start a continuous tone on the selected channel"""
        if not self.server:
            return
        
        # Stop existing tone if any
        self.stop_tone()
        
        # Get selected channel
        channel = self.tone_channel.value()
        
        # Create frequency based on channel
        freq = 440 * (1 + channel * 0.25)
        
        # Create and start the tone
        sine = pyo.Sine(freq=freq, mul=0.3)
        output = pyo.Mix(sine)
        output.out(chnl=channel)
        
        # Store references
        self.tone_gen = (sine, output)
        
        # Update UI
        self.tone_start.setEnabled(False)
        self.tone_stop.setEnabled(True)
        self.status_label.setText(f"Playing continuous tone on channel {channel}")
    
    def stop_tone(self):
        """Stop the continuous tone if playing"""
        if self.tone_gen:
            sine, output = self.tone_gen
            sine.stop()
            output.stop()
            self.tone_gen = None
            
            # Update UI
            self.tone_start.setEnabled(True)
            self.tone_stop.setEnabled(True)
            self.status_label.setText("Tone stopped")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SimpleChannelTest()
    window.show()
    sys.exit(app.exec_())
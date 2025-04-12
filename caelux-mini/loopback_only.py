#!/usr/bin/env python3
"""
Caelux Mini - Loopback Only Edition
A severely trimmed down version that tries to use ONLY the Loopback Audio 2 device
"""

import pyo
import mido
import time
import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton

class LoopbackTest(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Loopback Audio Test")
        self.resize(400, 300)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Add status label
        self.status = QLabel("Initializing...")
        layout.addWidget(self.status)
        
        # Add test buttons for each possible device number
        for i in range(10):
            button = QPushButton(f"Test Device {i}")
            button.clicked.connect(lambda checked, idx=i: self.test_device(idx))
            layout.addWidget(button)
        
        # Try to automatically find and use Loopback Audio
        self.find_loopback()
    
    def find_loopback(self):
        """Try to find Loopback Audio device"""
        self.status.setText("Searching for Loopback Audio...")
        
        try:
            # Get device info
            devices = pyo.pa_get_output_devices()
            self.status.setText(f"Device list: {devices}")
            
            # Find the Loopback device
            loopback_index = None
            
            if isinstance(devices, dict):
                # Dict format
                for idx, name in devices.items():
                    if "loopback" in name.lower():
                        loopback_index = idx
                        self.status.setText(f"Found Loopback at index {idx}: {name}")
                        break
            elif isinstance(devices, tuple) and len(devices) == 2:
                # ([names], [indices]) format
                names = devices[0]
                indices = devices[1]
                for i, name in enumerate(names):
                    if isinstance(name, str) and "loopback" in name.lower():
                        if i < len(indices):
                            loopback_index = indices[i]
                            self.status.setText(f"Found Loopback at index {loopback_index}: {name}")
                            break
            
            if loopback_index is not None:
                # Try to use it
                self.test_device(loopback_index)
            else:
                self.status.setText("No Loopback device found. Try manual buttons.")
        except Exception as e:
            self.status.setText(f"Error finding devices: {e}")
    
    def test_device(self, device_index):
        """Test a specific device index"""
        self.status.setText(f"Testing device {device_index}...")
        
        try:
            # Create server
            s = pyo.Server(nchnls=4)  # Request 4 channels 
            s.boot()
            
            # Show default device
            default_device = s.getOutputDevice()
            self.status.setText(f"Default device: {default_device}, trying to set: {device_index}")
            
            # Set device
            s.setOutputDevice(device_index)
            current_device = s.getOutputDevice()
            
            if current_device == device_index:
                self.status.setText(f"Successfully set device to {device_index}")
            else:
                self.status.setText(f"Failed to set device. Requested {device_index}, got {current_device}")
                return
            
            # Start server
            s.start()
            
            # Test channels
            channels = s.getNchnls()
            self.status.setText(f"Device {device_index} has {channels} channels")
            
            # Generate test tones for each channel
            for ch in range(channels):
                freq = 440 * (1 + ch * 0.25)  # Different frequency for each channel
                
                # Create a mixer to route to a specific channel
                self.status.setText(f"Playing on channel {ch} ({freq} Hz)...")
                sine = pyo.Sine(freq=freq, mul=0.3)
                mixer = pyo.Mixer(voices=1, chnls=channels)
                mixer.addInput(0, sine)
                mixer.setAmp(0, ch, 1.0)
                mixer.out()
                
                # Let it play briefly
                time.sleep(0.5)
                
                # Stop
                sine.stop()
                mixer.stop()
            
            # Final status
            self.status.setText(f"Device {device_index} test complete. Channels: {channels}")
            
            # Clean up
            s.stop()
            s.shutdown()
            
        except Exception as e:
            self.status.setText(f"Error testing device {device_index}: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LoopbackTest()
    window.show()
    sys.exit(app.exec_())
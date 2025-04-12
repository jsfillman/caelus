#!/usr/bin/env python3
"""
Caelux Mini Synthesizer - 8-Channel Loopback Version
Fixed to use Loopback Audio 2 (device 5) with 8 channels
"""

import pyo
import mido
import random
import atexit
import sys
import time
import os

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
PATCH_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "last_patch.yaml")

# Hardcoded audio settings
LOOPBACK_DEVICE_INDEX = 5
LOOPBACK_DEVICE_NAME = "Loopback Audio 2"
NCHNLS = 8  # 8 channels
SR = 44100
BS = 256

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Caelux Mini - {LOOPBACK_DEVICE_NAME} ({NCHNLS} channels)")
        
        # Initialize audio server first - HARDCODED FOR LOOPBACK AUDIO 2
        self.server = None
        self.particle = None
        self.init_audio_server()
        
        # Only create particle if server was successfully created and started
        if self.server and hasattr(self.server, 'getIsStarted') and self.server.getIsStarted():
            print("Audio server initialized and started - creating particle")
            try:
                # Initialize the Particle (which contains oscillators)
                self.particle = Particle(self.server)
                print(f"Particle created and initialized: {self.particle.initialized}")
            except Exception as e:
                print(f"Error creating particle: {e}")
                self.particle = None
        else:
            print("Audio server not started - cannot create particle")
            self.particle = None
        
        # Initialize the MIDI handler
        self.midi_handler = MidiHandler()
        
        # Connect MIDI signals to particle
        self.connect_midi_to_particle()
        
        # Create main layout
        main_layout = QHBoxLayout()
        
        # Create tab widget for vertical tabs
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.West)  # Put tabs on the left side
        
        # Add Global tab (always show this)
        global_tab = self.create_global_tab()
        self.tabs.addTab(global_tab, "G")
        self.tabs.setTabToolTip(0, "Global Settings")
        
        # Only create oscillator UIs if server is properly running
        if self.server and hasattr(self.server, 'getIsStarted') and self.server.getIsStarted():
            print("Creating oscillator UI tabs")
            try:
                # Add Operator tab (OP1)
                self.op1_ui = OscillatorUI(self.server, "OP1", "operator")
                self.tabs.addTab(self.op1_ui, "O1")
                self.tabs.setTabToolTip(1, "Operator 1")
                
                # Add Carrier tab (CAR1)
                self.car1_ui = OscillatorUI(self.server, "CAR1", "carrier")
                self.tabs.addTab(self.car1_ui, "C1")
                self.tabs.setTabToolTip(2, "Carrier 1")
                
                # Add Carrier tab (CAR2)
                self.car2_ui = OscillatorUI(self.server, "CAR2", "carrier")
                self.tabs.addTab(self.car2_ui, "C2")
                self.tabs.setTabToolTip(3, "Carrier 2")
            except Exception as e:
                print(f"Error creating oscillator UI: {e}")
                # Add a message tab instead
                error_tab = QWidget()
                error_layout = QVBoxLayout()
                error_label = QLabel("Error: Audio server not initialized properly.\nOnly global settings are available.")
                error_layout.addWidget(error_label)
                error_tab.setLayout(error_layout)
                self.tabs.addTab(error_tab, "Error")
        else:
            # Add a message tab instead
            print("Cannot create oscillator UIs - server not running")
            error_tab = QWidget()
            error_layout = QVBoxLayout()
            error_label = QLabel("Error: Audio server not initialized.\nOnly global settings are available.")
            error_layout.addWidget(error_label)
            error_tab.setLayout(error_layout)
            self.tabs.addTab(error_tab, "Error")
        
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
        if not hasattr(self, 'midi_handler'):
            print("No MIDI handler available")
            return
            
        if not hasattr(self, 'particle') or not self.particle or not hasattr(self.particle, 'initialized') or not self.particle.initialized:
            print("Particle not initialized, cannot connect MIDI signals")
            # At least connect the note on signal to our handler (which has error checking)
            try:
                # Disconnect first to avoid duplicate connections
                try:
                    self.midi_handler.note_on_signal.disconnect(self.handle_note_on)
                except:
                    pass
                # Connect
                self.midi_handler.note_on_signal.connect(self.handle_note_on)
            except Exception as e:
                print(f"Error connecting MIDI note on signal: {e}")
            return
        
        try:
            # Connect note signals
            # Disconnect first to avoid duplicate connections
            try:
                self.midi_handler.note_on_signal.disconnect(self.handle_note_on)
            except:
                pass
            self.midi_handler.note_on_signal.connect(self.handle_note_on)
            
            try:
                self.midi_handler.note_off_signal.disconnect()
            except:
                pass
            self.midi_handler.note_off_signal.connect(self.particle.note_off)
            
            # Connect other MIDI signals as needed
            try:
                self.midi_handler.pitch_bend_signal.disconnect()
            except:
                pass
            self.midi_handler.pitch_bend_signal.connect(self.particle.pitch_bend)
            
            print("MIDI signals connected successfully")
        except Exception as e:
            print(f"Error connecting MIDI signals: {e}")
        
    def connect_bypass_signals(self):
        """Connect UI bypass signals to oscillator bypass methods"""
        if not hasattr(self, 'particle') or not self.particle or not hasattr(self.particle, 'initialized') or not self.particle.initialized:
            print("Cannot connect bypass signals - particle not initialized")
            return
            
        try:
            print(f"Connecting bypass signals for oscillators: {list(self.particle.oscillators.keys())}")
        except:
            print("Cannot list oscillators")
            return
            
        try:
            # First disconnect any existing connections to avoid duplicates
            self._disconnect_bypass_signals()
            
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
                
                # Connect routing signals
                self.car1_ui.routing_changed_signal.connect(self.handle_routing_change)
                self.car1_ui.channel_routing_changed_signal.connect(self.handle_channel_routing_change)
                
            # Connect CAR2 bypass signals
            if "CAR2" in self.particle.oscillators:
                car2 = self.particle.oscillators["CAR2"]
                self.car2_ui.osc_bypass_toggled.connect(lambda state: car2.set_bypass('osc', state))
                self.car2_ui.freq_bypass_toggled.connect(lambda state: car2.set_bypass('freq', state))
                self.car2_ui.amp_bypass_toggled.connect(lambda state: car2.set_bypass('amp', state))
                self.car2_ui.filter_bypass_toggled.connect(lambda state: car2.set_bypass('filter', state))
                self.car2_ui.delay_bypass_toggled.connect(lambda state: car2.set_bypass('delay', state))
                
                # Connect panner signals
                self.car2_ui.pan_position_changed_signal.connect(car2.set_pan_position)
                self.car2_ui.stereo_width_changed_signal.connect(car2.set_stereo_width)
                self.car2_ui.autopan_toggled_signal.connect(lambda enabled: car2.set_autopan(enabled))
                self.car2_ui.autopan_rate_changed_signal.connect(lambda rate: car2.set_autopan(car2.use_autopan, rate))
                
                # Connect routing signals
                self.car2_ui.routing_changed_signal.connect(self.handle_routing_change)
                self.car2_ui.channel_routing_changed_signal.connect(self.handle_channel_routing_change)
                
            print("Bypass signals connected")
        except Exception as e:
            print(f"Error connecting bypass signals: {e}")
            
    def _disconnect_bypass_signals(self):
        """Disconnect existing bypass signals to prevent duplicate connections"""
        try:
            # Disconnect OP1 signals
            try:
                self.op1_ui.osc_bypass_toggled.disconnect()
                self.op1_ui.freq_bypass_toggled.disconnect()
                self.op1_ui.amp_bypass_toggled.disconnect()
                self.op1_ui.filter_bypass_toggled.disconnect()
                self.op1_ui.delay_bypass_toggled.disconnect()
                self.op1_ui.pan_position_changed_signal.disconnect()
                self.op1_ui.stereo_width_changed_signal.disconnect()
                self.op1_ui.autopan_toggled_signal.disconnect()
                self.op1_ui.autopan_rate_changed_signal.disconnect()
            except:
                pass
                
            # Disconnect CAR1 signals
            try:
                self.car1_ui.osc_bypass_toggled.disconnect()
                self.car1_ui.freq_bypass_toggled.disconnect()
                self.car1_ui.amp_bypass_toggled.disconnect()
                self.car1_ui.filter_bypass_toggled.disconnect()
                self.car1_ui.delay_bypass_toggled.disconnect()
                self.car1_ui.pan_position_changed_signal.disconnect()
                self.car1_ui.stereo_width_changed_signal.disconnect()
                self.car1_ui.autopan_toggled_signal.disconnect()
                self.car1_ui.autopan_rate_changed_signal.disconnect()
                self.car1_ui.routing_changed_signal.disconnect()
                self.car1_ui.channel_routing_changed_signal.disconnect()
            except:
                pass
                
            # Disconnect CAR2 signals
            try:
                self.car2_ui.osc_bypass_toggled.disconnect()
                self.car2_ui.freq_bypass_toggled.disconnect()
                self.car2_ui.amp_bypass_toggled.disconnect()
                self.car2_ui.filter_bypass_toggled.disconnect()
                self.car2_ui.delay_bypass_toggled.disconnect()
                self.car2_ui.pan_position_changed_signal.disconnect()
                self.car2_ui.stereo_width_changed_signal.disconnect()
                self.car2_ui.autopan_toggled_signal.disconnect()
                self.car2_ui.autopan_rate_changed_signal.disconnect()
                self.car2_ui.routing_changed_signal.disconnect()
                self.car2_ui.channel_routing_changed_signal.disconnect()
            except:
                pass
        except Exception as e:
            print(f"Error disconnecting signals: {e}")
            
    def handle_routing_change(self, source, destination, amount):
        """Handle modulation routing change from UI"""
        if not hasattr(self, 'particle') or not self.particle or not hasattr(self.particle, 'initialized') or not self.particle.initialized:
            print(f"Cannot set routing {source} -> {destination}: particle not initialized")
            return
            
        try:
            # Update the particle's modulation matrix
            self.particle.set_modulation(source, destination, amount)
        except Exception as e:
            print(f"Error setting modulation routing: {e}")
        
    def handle_channel_routing_change(self, oscillator_name, channel, amount):
        """Handle channel routing change from UI"""
        if not hasattr(self, 'particle') or not self.particle or not hasattr(self.particle, 'initialized') or not self.particle.initialized:
            print(f"Cannot set channel routing for {oscillator_name}: particle not initialized")
            return
            
        try:
            # Update the oscillator's channel routing
            self.particle.set_channel_routing(oscillator_name, channel, amount)
        except Exception as e:
            print(f"Error setting channel routing: {e}")
    
    def handle_note_on(self, note, velocity):
        """Handle note on by passing parameters from UI"""
        # Print for debugging
        print(f"MIDI Note ON received: note={note}, velocity={velocity}")
        
        # Check if particle exists and is initialized
        if not hasattr(self, 'particle') or not self.particle or not hasattr(self.particle, 'note_on'):
            print("Cannot trigger note: particle not initialized")
            return
            
        # Create a dictionary of UI references for each oscillator
        ui_dict = {
            "OP1": self.op1_ui,
            "CAR1": self.car1_ui,
            "CAR2": self.car2_ui
        }
        
        try:
            # Trigger note-on on the particle with UI references
            self.particle.note_on(note, velocity, ui_dict)
        except Exception as e:
            print(f"Error triggering note: {e}")
            # Try to recover by recreating the particle
            try:
                if self.server and self.server.getIsStarted():
                    print("Attempting to recover by reinitializing particle...")
                    self.particle = Particle(self.server)
                    self.connect_bypass_signals()
            except:
                print("Could not recover particle after error")
    
    def init_audio_server(self):
        """Initialize audio server with HARDCODED Loopback Audio 2 device"""
        try:
            print(f"CREATING HARDCODED AUDIO SERVER FOR {LOOPBACK_DEVICE_NAME} (index {LOOPBACK_DEVICE_INDEX})")
            
            # Create the server with our parameters, disable input (duplex=0)
            try:
                print(f"Creating server with device={LOOPBACK_DEVICE_INDEX}, SR={SR}, BS={BS}, NCHNLS={NCHNLS}")
                self.server = pyo.Server(
                    sr=SR, 
                    buffersize=BS,
                    nchnls=NCHNLS,
                    duplex=0  # Disable input to avoid warnings
                )
                print("Server created successfully")
                
                # Boot the server
                print("Booting the server...")
                self.server.boot()
                print("Server booted successfully")
                
                # Set the device before starting - CRITICAL
                print(f"Setting output device to {LOOPBACK_DEVICE_INDEX}...")
                self.server.setOutputDevice(LOOPBACK_DEVICE_INDEX)
                print(f"Output device set to {LOOPBACK_DEVICE_INDEX}")
                
                # Start the server
                print("Starting the server...")
                self.server.start()
                print("Server started successfully")
                
                # Print actual channels after setting device
                print(f"Actual channels: {self.server.getNchnls()}")
                
                # Test each channel briefly
                self.test_audio_channels(self.server.getNchnls())
                
            except Exception as e:
                print(f"Server creation failed: {e}")
                QMessageBox.critical(self, "Audio Error", 
                    f"Could not initialize audio with {LOOPBACK_DEVICE_NAME}:\n\n{e}\n\nThe synthesizer will not produce sound.")
                self.server = None
                
        except Exception as e:
            print(f"Fatal error initializing audio: {e}")
            QMessageBox.critical(self, "Audio Error", 
                f"Fatal error initializing audio: {e}\n\nThe synthesizer will not produce sound.")
            self.server = None
    
    def test_audio_channels(self, num_channels):
        """Test each audio channel with a sine tone"""
        if not self.server or not self.server.getIsStarted():
            return
            
        print(f"Testing {num_channels} audio channels...")
        
        # Short duration to avoid long startup
        duration = 0.1  # seconds per channel
        
        # Create a single test tone
        test_sine = pyo.Sine(freq=440, mul=0.2)
        
        # Play on each channel sequentially
        for channel in range(num_channels):
            try:
                # Create a gate for just this one channel
                channel_selector = pyo.Sig(0, mul=test_sine)
                
                # Route it to the right channel
                output = pyo.Mix(channel_selector, voices=1)
                output.out(chnl=channel)
                
                # Turn on the signal
                channel_selector.mul = 1.0
                
                # Let it play briefly
                time.sleep(duration)
                
                # Turn off the signal
                channel_selector.mul = 0
                time.sleep(0.05)  # Small gap between tones
                
                # Clean up
                output.stop()
            except Exception as e:
                print(f"Error testing channel {channel}: {e}")
        
        # Clean up
        test_sine.stop()
        print("Channel test complete")
    
    def create_global_tab(self):
        """Create a simplified Global settings tab with only MIDI selection"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Audio Status
        audio_group = QGroupBox("Audio Status")
        audio_layout = QVBoxLayout()
        
        status_text = f"Using {LOOPBACK_DEVICE_NAME} (index {LOOPBACK_DEVICE_INDEX})\n"
        status_text += f"Channels: {NCHNLS}\n"
        status_text += f"Sample Rate: {SR} Hz, Buffer Size: {BS}"
        
        self.audio_status_label = QLabel(status_text)
        self.audio_status_label.setStyleSheet("font-weight: bold; color: green;")
        audio_layout.addWidget(self.audio_status_label)
        
        # Add test button
        self.test_channel_button = QPushButton("Test Audio Channels")
        self.test_channel_button.clicked.connect(self.test_audio_channels_ui)
        audio_layout.addWidget(self.test_channel_button)
        
        # Add channel routing info
        routing_label = QLabel("Channel Mapping:\n" +
                            "0: Front Left    1: Front Right\n" +
                            "2: Front Center  3: LFE\n" +
                            "4: Rear Left     5: Rear Right\n" +
                            "6: Side Left     7: Side Right")
        routing_label.setStyleSheet("font-family: monospace;")
        audio_layout.addWidget(routing_label)
        
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
            
    def test_audio_channels_ui(self):
        """Handle the Test Audio Channels button click with user feedback"""
        if not self.server or not self.server.getIsStarted():
            QMessageBox.warning(self, "Audio Test", "Audio server is not running. Cannot test channels.")
            return
            
        # Get the number of channels from the server - safely
        try:
            num_channels = self.server.getNchnls()
        except Exception as e:
            print(f"Could not get channel count: {e}")
            num_channels = NCHNLS  # Use hardcoded value
        
        # Create a message box to show during the test
        msg = QMessageBox(self)
        msg.setWindowTitle("Audio Channel Test")
        msg.setText(f"Testing {num_channels} audio channels...")
        msg.setStandardButtons(QMessageBox.NoButton)
        
        # Set informative text
        msg.setInformativeText(f"Device: {LOOPBACK_DEVICE_NAME}\nChannels: {num_channels}\n\nListen for test tones on each channel.")
        
        # Show the message box without blocking
        msg.show()
        
        # Schedule the test to run after the UI has updated
        QTimer.singleShot(100, lambda: self._run_channel_test(num_channels, msg))
    
    def _run_channel_test(self, num_channels, msg_box):
        """Run the actual channel test and update the message box"""
        if not self.server or not self.server.getIsStarted():
            msg_box.done(0)  # Close the message box
            return
        
        # Create a unique test signal for each channel with different frequencies
        # This makes it easier to tell which channel is which by ear
        base_freq = 440  # A4
        test_freqs = [
            base_freq,           # Channel 0 (Front Left): A4 (440 Hz)
            base_freq * 1.25,    # Channel 1 (Front Right): E5 (550 Hz)
            base_freq * 1.5,     # Channel 2 (Center): A5 (660 Hz)
            base_freq * 1.75,    # Channel 3 (LFE): E6 (770 Hz) 
            base_freq * 2.0,     # Channel 4 (Rear Left): A6 (880 Hz)
            base_freq * 2.25,    # Channel 5 (Rear Right): C#7 (1100 Hz)
            base_freq * 2.5,     # Channel 6 (Side Left): A7 (1320 Hz) 
            base_freq * 2.75     # Channel 7 (Side Right): E8 (1540 Hz)
        ]
        
        channel_names = [
            "Front Left",
            "Front Right",
            "Front Center",
            "LFE / Subwoofer",
            "Rear Left",
            "Rear Right",
            "Side Left",
            "Side Right"
        ]
        
        # Test tone duration
        duration = 0.5  # seconds per channel
        
        # Create test tones for each channel with different frequencies
        test_sines = []
        for i in range(min(num_channels, len(test_freqs))):
            test_sines.append(pyo.Sine(freq=test_freqs[i], mul=0.3))
        
        # Use a timer to test each channel sequentially with UI updates
        current_channel = [0]  # Use list for mutable closure
        
        def test_next_channel():
            channel = current_channel[0]
            
            # If we've tested all channels, clean up and close dialog
            if channel >= num_channels:
                # Clean up all test tones
                for sine in test_sines:
                    sine.stop()
                
                # Update message and add a close button
                msg_box.setText("Channel Test Complete")
                msg_box.setStandardButtons(QMessageBox.Ok)
                return
            
            # Update the message for the current channel
            channel_name = channel_names[channel] if channel < len(channel_names) else f"Channel {channel}"
            msg_box.setText(f"Testing {channel_name} (Channel {channel})")
            
            try:
                # Create a gate for just this one channel
                channel_selector = pyo.Sig(0, mul=test_sines[channel if channel < len(test_sines) else 0])
                
                # Route it to the right channel
                output = pyo.Mix(channel_selector, voices=1)
                output.out(chnl=channel)
                
                # Turn on the signal
                channel_selector.mul = 1.0
                
                # Schedule turning off the signal after duration
                QTimer.singleShot(int(duration * 1000), lambda: channel_selector.setValue(0))
                
                # Schedule clean-up and next channel
                QTimer.singleShot(int((duration + 0.2) * 1000), lambda: output.stop())
                QTimer.singleShot(int((duration + 0.3) * 1000), lambda: 
                    [current_channel.__setitem__(0, current_channel[0] + 1), test_next_channel()])
                
            except Exception as e:
                print(f"Error testing channel {channel}: {e}")
                # Move to next channel on error
                current_channel[0] += 1
                QTimer.singleShot(100, test_next_channel)
        
        # Start the test sequence
        test_next_channel()
    
    def save_patch(self):
        """Save the current patch to file"""
        try:
            # Create a patch dictionary with parameters from all oscillators
            patch = {
                "op1": self._get_osc_params(self.op1_ui),
                "car1": self._get_osc_params(self.car1_ui),
                "car2": self._get_osc_params(self.car2_ui)
            }
            
            # Add modulation matrix
            if hasattr(self, 'particle') and self.particle.initialized:
                patch["modulation_matrix"] = self.particle.get_routing_matrix()
            
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
            
            if "car2" in patch:
                self._set_osc_params(self.car2_ui, patch["car2"])
                # Apply bypass states to the actual oscillator
                if "CAR2" in self.particle.oscillators:
                    car2 = self.particle.oscillators["CAR2"]
                    # Apply bypass states
                    if "bypass" in patch["car2"]:
                        for section, state in patch["car2"]["bypass"].items():
                            car2.set_bypass(section, state)
                    # Apply panner settings
                    if "pan_position" in patch["car2"]:
                        car2.set_pan_position(patch["car2"]["pan_position"])
                    if "stereo_width" in patch["car2"]:
                        car2.set_stereo_width(patch["car2"]["stereo_width"])
                    if "autopan_enabled" in patch["car2"]:
                        car2.set_autopan(patch["car2"]["autopan_enabled"],
                                        patch["car2"].get("autopan_rate", None))
            
            # Apply modulation matrix if present
            if "modulation_matrix" in patch and hasattr(self, 'particle'):
                self.particle.set_all_modulation(patch["modulation_matrix"])
            
            # Apply channel routing if present
            for osc_key, osc_data in patch.items():
                if osc_key in ["op1", "car1", "car2"] and "channel_routing" in osc_data:
                    osc_name = osc_key.upper()
                    for channel, amount in osc_data["channel_routing"].items():
                        try:
                            channel_num = int(channel.split("_")[1])
                            self.particle.set_channel_routing(osc_name, channel_num, amount)
                        except (ValueError, IndexError, AttributeError):
                            pass
                
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
        
        # Get modulation matrix amounts if present (for carriers only)
        if hasattr(ui, 'mod_amount_sliders'):
            params["modulation"] = {}
            for source, slider_layout in ui.mod_amount_sliders.items():
                params["modulation"][source] = slider_layout.itemAt(1).widget().value()
                
            # For backward compatibility, also save old mod_amount
            if hasattr(ui, 'mod_amount'):
                params["mod_amount"] = ui.mod_amount.itemAt(1).widget().value()
        elif hasattr(ui, 'mod_amount'):
            # For backward compatibility
            params["mod_amount"] = ui.mod_amount.itemAt(1).widget().value()
        
        # Channel routing for carriers
        if ui.osc_type == "carrier" and hasattr(ui, 'channel_sliders'):
            params["channel_routing"] = {}
            for i, slider_layout in enumerate(ui.channel_sliders):
                params["channel_routing"][f"channel_{i}"] = slider_layout.itemAt(1).widget().value()
        
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
        
        # Set modulation matrix amounts if present (for carriers only)
        if hasattr(ui, 'mod_amount_sliders') and "modulation" in params:
            for source, amount in params["modulation"].items():
                if source in ui.mod_amount_sliders:
                    self._set_value(ui.mod_amount_sliders[source], amount)
        
        # For backward compatibility
        if hasattr(ui, 'mod_amount') and "mod_amount" in params:
            self._set_value(ui.mod_amount, params.get("mod_amount"))
            
        # Set channel routing for carriers
        if ui.osc_type == "carrier" and hasattr(ui, 'channel_sliders') and "channel_routing" in params:
            for channel_name, amount in params["channel_routing"].items():
                try:
                    idx = int(channel_name.split("_")[1])
                    if 0 <= idx < len(ui.channel_sliders):
                        self._set_value(ui.channel_sliders[idx], amount)
                except (ValueError, IndexError):
                    pass
                
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
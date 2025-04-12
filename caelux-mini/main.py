import pyo
import mido
import random
import atexit
import sys
import time

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
        
        # Initialize audio server first
        self.server = None
        self.particle = None  # Initialize to None
        self.init_audio_server()
        
        # Only create particle if server was successfully created and started
        if self.server and hasattr(self.server, 'getIsStarted') and self.server.getIsStarted():
            print("Audio server initialized and started - creating particle")
            try:
                # Initialize the Particle (which contains 2 oscillators)
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
        """Initialize audio server with default settings"""
        try:
            # Get available audio devices first
            device_info = {}  # Will hold device info if discovered
            default_device = 0  # Default fallback
            
            # Try multiple methods to get audio device info
            print("\nDISCOVERING AUDIO DEVICES:")
            
            # Method 1: Try pa_get_output_devices (newer API with different formats)
            try:
                print("Method 1: Using pa_get_output_devices():")
                raw_info = pyo.pa_get_output_devices()
                print(f"Raw output device info: {raw_info}")
                
                # Handle different return formats
                if isinstance(raw_info, dict):
                    # Case 1: Dictionary format
                    device_info = raw_info
                    print("  Dictionary format detected")
                    for idx, name in device_info.items():
                        print(f"  {idx}: {name}")
                        
                    # Look for multichannel device
                    for idx, name in device_info.items():
                        if isinstance(name, str) and any(term in name.lower() for term in ["quad", "surround", "5.1", "7.1", "8", "loopback audio 2"]):
                            print(f"Found likely multichannel device: {name} (index {idx})")
                            default_device = idx
                            break
                            
                elif isinstance(raw_info, tuple) or isinstance(raw_info, list):
                    # Case 2: Tuple or list format
                    print("  List/Tuple format detected")
                    device_info = {}
                    
                    # Check if this is the specific format: ([names], [indices])
                    if len(raw_info) == 2 and isinstance(raw_info[0], list) and isinstance(raw_info[1], list):
                        print("  Detected specific format: ([names], [indices])")
                        names = raw_info[0]
                        indices = raw_info[1]
                        
                        # Map each name to its corresponding index
                        for i in range(len(names)):
                            if i < len(indices):
                                idx = indices[i]
                                name = names[i]
                                device_info[idx] = name
                                print(f"  {idx}: {name}")
                                
                                # Check for multichannel
                                if isinstance(name, str) and any(term in name.lower() for term in ["quad", "surround", "5.1", "7.1", "8", "loopback audio 2"]):
                                    print(f"Found likely multichannel device: {name} (index {idx})")
                                    default_device = idx
                    else:
                        # Standard list/tuple processing
                        for i, name in enumerate(raw_info):
                            if name:  # Skip empty entries
                                device_info[i] = name
                                print(f"  {i}: {name}")
                                
                                # Check for multichannel
                                if isinstance(name, str) and any(term in name.lower() for term in ["quad", "surround", "5.1", "7.1", "8", "loopback audio 2"]):
                                    print(f"Found likely multichannel device: {name} (index {i})")
                                    default_device = i
                                    
                # After detecting, try to check if the found device is valid
                print(f"Checking if device {default_device} is valid...")
                
                # Create a test server to check device validity
                try:
                    print("Creating test server to verify device")
                    test_server = None
                    try:
                        # Try creating with no device parameter
                        test_server = pyo.Server()
                        print("Created test server")
                        
                        # Try setting device
                        try:
                            test_server.setOutputDevice(default_device)
                            print(f"Device {default_device} appears valid")
                        except Exception as e:
                            print(f"Device {default_device} not valid: {e}")
                            default_device = 0  # Fall back to default device
                    except:
                        print("Could not create test server")
                        
                    # Clean up test server
                    if test_server is not None:
                        del test_server
                except Exception as e:
                    print(f"Error testing device: {e}")
                    
                # Additional formats could be handled here
                else:
                    print(f"  Unknown format: {type(raw_info)}")
                    # Try to extract something useful anyway
                    try:
                        device_info = {}
                        if hasattr(raw_info, "__iter__"):
                            for i, item in enumerate(raw_info):
                                device_info[i] = str(item)
                                print(f"  {i}: {item}")
                    except:
                        print("  Couldn't interpret data format")
            except Exception as e:
                print(f"Method 1 (pa_get_output_devices) failed: {e}")
                
            # Method 2: If that failed, try pa_get_devices_infos (older API)
            if not device_info:
                try:
                    print("Method 2: Using pa_get_devices_infos:")
                    audio_info = pyo.pa_get_devices_infos()
                    for i, dev in enumerate(audio_info):
                        try:
                            if isinstance(dev, dict) and 'name' in dev:
                                name = dev['name']
                                device_info[i] = name
                                print(f"  {i}: {name}")
                                # Check for multichannel
                                if any(term in name.lower() for term in ["quad", "surround", "5.1", "7.1", "8", "loopback audio 2"]):
                                    print(f"Found likely multichannel device: {name} (index {i})")
                                    default_device = i
                            # Older method for nested dicts
                            else:
                                for key, value in dev.items():
                                    if isinstance(value, dict) and 'name' in value:
                                        name = value['name']
                                        idx = int(key) if key.isdigit() else i
                                        device_info[idx] = name
                                        print(f"  {idx}: {name}")
                                        # Check for multichannel
                                        if any(term in name.lower() for term in ["quad", "surround", "5.1", "7.1", "8", "loopback audio 2"]):
                                            print(f"Found likely multichannel device: {name} (index {idx})")
                                            default_device = idx
                        except:
                            pass
                except Exception as e:
                    print(f"Method 2 (pa_get_devices_infos) failed: {e}")
                    
            # Get device name if available
            device_name = device_info.get(default_device, f"Device {default_device}")
            print(f"Selected default device: {default_device} ({device_name})")
            
            # Determine if multichannel
            nchnls = 4 if device_info and any(term in device_info.get(default_device, "").lower() 
                        for term in ["quad", "surround", "5.1", "7.1", "8", "loopback audio 2"]) else 2
            
            # Initialize server with explicit device selection
            print(f"Creating initial server with device {default_device} ({device_name}) and {nchnls} channels")
            
            print(f"Creating server with simplified params...")
            # Create the server with minimal parameters - some versions of pyo have different parameter names
            try:
                # Try the most standard approach
                self.server = pyo.Server(nchnls=nchnls)
                print("Created server with nchnls parameter")
            except Exception as e:
                print(f"Failed with standard params: {e}")
                # Fall back to defaults
                self.server = pyo.Server()
                print("Created server with default parameters")
                
            # Boot the server first before setting device
            try:
                print("Booting the server...")
                self.server.boot()
                print("Server booted successfully")
            except Exception as e:
                print(f"Error booting server: {e}")
                
            # Try to set device after creation
            print(f"Setting output device to {default_device} after creation")
            try:
                self.server.setOutputDevice(default_device)  # Try to set device after server creation
                print(f"Successfully set output device to {default_device}")
            except Exception as e:
                print(f"Could not set output device: {e}")
                
            # Start the server
            try:
                print("Starting the server...")
                self.server.start()
                print("Server started successfully")
            except Exception as e:
                print(f"Error starting server: {e}")
                
        except Exception as e:
            print(f"Could not get audio device info: {e}, using default settings")
            
            try:
                # Fall back to default with minimal parameters
                print("Creating server with default parameters...")
                self.server = pyo.Server(nchnls=2, buffersize=256, sr=44100)
                
                # Try to boot and start the server
                print("Booting audio server...")
                self.server.boot()
                print("Starting audio server...")
                self.server.start()
                print("Server started with default settings")
            except Exception as e:
                print(f"Fatal error creating default server: {e}")
            
            # Print current audio settings for debugging
            print(f"Audio initialized - SR: {self.server.getSamplingRate()}, BS: {self.server.getBufferSize()}")
            
            # Get and print the actual device that was used
            try:
                actual_device = self.server.getOutputDevice()
                device_info = pyo.pa_get_output_devices()
                device_name = device_info.get(actual_device, "Unknown")
                print(f"Actual output device: {device_name} (index: {actual_device})")
            except Exception as e:
                print(f"Could not get output device info: {e}")
                
            # Print audio server status
            print(f"Audio server is running: {self.server.getIsStarted()}")
            print(f"Audio server number of channels: {self.server.getNchnls()}")
                
            # Test each channel
            print("Testing initial audio setup:")
            self.test_audio_channels(self.server.getNchnls())
                
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
        
        # Add status label for current audio device
        self.audio_device_status = QLabel("")
        self.audio_device_status.setStyleSheet("color: #666; font-style: italic;")
        
        # Get available audio outputs from pyo
        if self.server:
            try:
                # Different methods to get device info depending on pyo version
                print("Trying multiple methods to get audio devices...")
                
                # Clear any existing devices
                self.audio_devices.clear()
                
                # Track which item should be selected (the current device)
                current_device = None
                try:
                    current_device = self.server.getOutputDevice()
                except:
                    pass
                current_idx = 0
                
                # Method 1: Try pa_get_output_devices (newer API with different formats)
                try:
                    print("Method 1: Using pa_get_output_devices():")
                    raw_info = pyo.pa_get_output_devices()
                    print(f"Raw output device info: {raw_info}")
                    
                    # Handle different return formats
                    if isinstance(raw_info, dict):
                        # Case 1: Dictionary format
                        print("  Dictionary format detected")
                        for idx, name in sorted(raw_info.items()):
                            print(f"  Adding device {idx}: {name}")
                            self.audio_devices.addItem(str(name), idx)
                            if idx == current_device:
                                current_idx = self.audio_devices.count() - 1
                                
                    elif isinstance(raw_info, tuple) or isinstance(raw_info, list):
                        # Case 2: Tuple or list format
                        print("  List/Tuple format detected")
                        
                        # Check if this is the specific format: ([names], [indices])
                        if len(raw_info) == 2 and isinstance(raw_info[0], list) and isinstance(raw_info[1], list):
                            print("  Detected specific format: ([names], [indices])")
                            names = raw_info[0]
                            indices = raw_info[1]
                            
                            # Add each device with its proper index
                            for i in range(len(names)):
                                if i < len(indices):
                                    idx = indices[i]
                                    name = names[i]
                                    print(f"  Adding device {idx}: {name}")
                                    self.audio_devices.addItem(str(name), idx)
                                    if idx == current_device:
                                        current_idx = self.audio_devices.count() - 1
                        else:
                            # Standard list format
                            for i, name in enumerate(raw_info):
                                if name:  # Skip empty entries
                                    print(f"  Adding device {i}: {name}")
                                    self.audio_devices.addItem(str(name), i)
                                    if i == current_device:
                                        current_idx = self.audio_devices.count() - 1
                        
                    # Additional formats could be handled here
                    else:
                        print(f"  Unknown format: {type(raw_info)}")
                        raise ValueError("Unhandled format")
                        
                except Exception as e:
                    print(f"Method 1 failed: {e}")
                
                # Method 2: If that failed, try pa_get_devices_infos()
                if self.audio_devices.count() == 0:
                    try:
                        print("Method 2: Using pa_get_devices_infos():")
                        audio_info = pyo.pa_get_devices_infos()
                        for i, dev in enumerate(audio_info):
                            try:
                                if isinstance(dev, dict) and 'name' in dev:
                                    name = dev['name']
                                    print(f"  Adding device {i}: {name}")
                                    self.audio_devices.addItem(name, i)
                                    if i == current_device:
                                        current_idx = self.audio_devices.count() - 1
                                else:
                                    # Look for devices with 'latency' key in nested dicts
                                    for key, value in dev.items():
                                        if isinstance(value, dict) and 'name' in value:
                                            name = value['name']
                                            device_index = int(key) if key.isdigit() else i
                                            print(f"  Adding device {device_index}: {name}")
                                            self.audio_devices.addItem(name, device_index)
                                            if device_index == current_device:
                                                current_idx = self.audio_devices.count() - 1
                            except:
                                pass
                    except Exception as e:
                        print(f"Method 2 failed: {e}")
                
                # Method 3: If all else fails, just add numbered devices
                if self.audio_devices.count() == 0:
                    print("Method 3: Adding generic device numbers")
                    for i in range(8):  # Add 8 generic devices
                        self.audio_devices.addItem(f"Audio Device {i}", i)
                        if i == current_device:
                            current_idx = self.audio_devices.count() - 1
                
                # Set selected device to match current server device
                if self.audio_devices.count() > 0:
                    self.audio_devices.setCurrentIndex(current_idx)
                    selected_name = self.audio_devices.currentText()
                    selected_id = self.audio_devices.currentData()
                    print(f"Set current audio device to: {selected_name} (index {selected_id})")
                
            except Exception as e:
                print(f"Error getting audio devices: {e}")
                self.audio_devices.addItem("Error listing audio devices", -1)
        else:
            self.audio_devices.addItem("No audio devices detected", -1)
        
        self.audio_devices.currentIndexChanged.connect(self.change_audio_device)
        
        audio_layout.addWidget(self.audio_devices_label)
        audio_layout.addWidget(self.audio_devices)
        audio_layout.addWidget(self.audio_device_status)
        
        # Update the status label with current device info
        self.update_audio_device_status()
        
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
        
        # Add channel test button
        self.test_channel_button = QPushButton("Test Audio Channels")
        self.test_channel_button.clicked.connect(self.test_audio_channels_ui)
        audio_layout.addWidget(self.test_channel_button)
        
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
        # But we can update the preview of what will be applied
        if index >= 0:
            device_name = self.audio_devices.currentText()
            device_id = self.audio_devices.currentData()
            
            # Update the status label to show the device will change after Apply
            self.audio_device_status.setText(f"Selected: {device_name} (ID: {device_id}) - Click Apply to activate")
            self.audio_device_status.setStyleSheet("color: #AA3300; font-style: italic;")
    
    def update_audio_device_status(self):
        """Update the audio device status label with current server information"""
        # Check if server exists first
        if not hasattr(self, 'server') or self.server is None:
            self.audio_device_status.setText("No audio server available")
            self.audio_device_status.setStyleSheet("color: #AA0000; font-style: italic;")
            return
            
        # Safely check if server is started
        server_started = False
        try:
            server_started = self.server.getIsStarted()
        except AttributeError:
            pass
        
        if not server_started:
            self.audio_device_status.setText("Audio server is not active")
            self.audio_device_status.setStyleSheet("color: #AA0000; font-style: italic;")
            return
            
        try:
            # Get the device ID safely
            device_id = None
            try:
                device_id = self.server.getOutputDevice()
            except (AttributeError, TypeError) as e:
                print(f"Could not get output device: {e}")
                pass
                
            # Get device info safely
            device_info = {}
            try:
                device_info = pyo.pa_get_output_devices()
            except:
                pass
                
            # Set device name
            device_name = "Unknown device"
            if device_id is not None:
                device_name = device_info.get(device_id, f"Device {device_id}")
            
            # Get other stats safely
            num_channels = 2  # Default
            try:
                num_channels = self.server.getNchnls()
            except:
                pass
                
            sr = 44100  # Default
            try:
                sr = self.server.getSamplingRate()
            except:
                pass
                
            bs = 256  # Default
            try:
                bs = self.server.getBufferSize()
            except:
                pass
            
            # Set a special color for multichannel devices
            if num_channels > 2:
                status_style = "color: #006600; font-style: italic; font-weight: bold;"
                channel_text = f"{num_channels} channels (surround)"
            else:
                status_style = "color: #666666; font-style: italic;"
                channel_text = f"{num_channels} channels (stereo)"
                
            self.audio_device_status.setText(f"Active: {device_name}\n{channel_text}, {sr} Hz, {bs} buffer")
            self.audio_device_status.setStyleSheet(status_style)
        except Exception as e:
            self.audio_device_status.setText(f"Error getting device info: {e}")
            self.audio_device_status.setStyleSheet("color: #AA0000; font-style: italic;")
    
    def apply_audio_settings(self):
        """Apply audio settings (requires restart)"""
        if not hasattr(self, 'server'):
            return
        
        # Get the selected audio device
        if self.audio_devices.currentIndex() < 0:
            return
            
        device_index = self.audio_devices.itemData(self.audio_devices.currentIndex())
        if device_index is None:
            return
            
        # Get the device name for logging/debugging
        device_name = self.audio_devices.currentText()
        print(f"Applying audio settings for device: {device_name} (index: {device_index})")
        
        sample_rate = int(self.sample_rate.currentText())
        buffer_size = int(self.buffer_size.currentText())
        
        # Try to determine number of channels directly from device name
        nchnls = 2  # Default to stereo
        if any(term in device_name.lower() for term in ["quad", "surround", "5.1", "7.1", "8", "loopback audio 2"]):
            nchnls = 4  # Set to quad for multichannel audio interfaces
            print(f"Detected multichannel device '{device_name}', setting to {nchnls} channels")
        
        # Warn that we need to restart the audio engine
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setText("Changing audio settings requires restarting the audio engine.")
        msg.setInformativeText("Any playing notes will be cut off. Continue?")
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        
        if msg.exec_() == QMessageBox.Cancel:
            return
        
        # Always use the complete server restart method - more reliable
        print("\nRestarting audio system with new settings...")
        
        try:
            # 1. Clean up the particle first
            if hasattr(self, 'particle') and self.particle:
                try:
                    print("Shutting down particle...")
                    self.particle.shutdown()
                    self.particle = None
                    print("Particle shut down successfully")
                except Exception as e:
                    print(f"Error shutting down particle: {e}")
                    self.particle = None
            
            # 2. Fully shutdown the server
            if hasattr(self, 'server') and self.server:
                try:
                    print("Shutting down server...")
                    server_stopped = False
                    
                    # Try to stop it gracefully first
                    try:
                        if hasattr(self.server, 'stop'):
                            self.server.stop()
                            print("Server stopped successfully")
                            server_stopped = True
                    except Exception as e:
                        print(f"Error stopping server: {e}")
                        
                    # If stop failed, try direct cleanup
                    if not server_stopped:
                        print("Trying direct cleanup...")
                        
                    # Clear the reference
                    self.server = None
                    print("Server reference cleared")
                except Exception as e:
                    print(f"Error during server shutdown: {e}")
                    # Make sure the reference is cleared
                    self.server = None
                
            # 3. Give the system time to release resources
            print("Waiting for resources to be released...")
            time.sleep(1.0)  # Increased wait time for better cleanup
            
            # 4. Create a completely fresh server with the new settings
            print(f"Creating fresh server with device {device_index} and {nchnls} channels...")
            
            # First attempt with proper device specification
            try:
                print(f"Attempt 1: Creating server with device={device_index}...")
                self.server = pyo.Server(
                    sr=sample_rate, 
                    buffersize=buffer_size,
                    nchnls=nchnls
                )
                print("Server created successfully")
                
                # Boot the server
                print("Booting the server...")
                self.server.boot()
                print("Server booted successfully")
                
                # Set the device before starting
                print(f"Setting output device to {device_index}...")
                self.server.setOutputDevice(device_index)
                print(f"Output device set to {device_index}")
                
                # Start the server
                print("Starting the server...")
                self.server.start()
                print("Server started successfully")
                
            except Exception as e:
                print(f"First server creation attempt failed: {e}")
                
                # Second attempt with minimal parameters
                try:
                    print("Attempt 2: Creating server with minimal parameters...")
                    self.server = pyo.Server(nchnls=nchnls)
                    print("Server created with minimal parameters")
                    
                    # Boot first
                    self.server.boot()
                    print("Server booted")
                    
                    # Set parameters after booting
                    try:
                        self.server.setOutputDevice(device_index)
                    except:
                        print("Could not set device")
                        
                    # Start the server
                    self.server.start()
                    print("Server started")
                    
                except Exception as e:
                    print(f"Second server creation attempt failed: {e}")
                    
                    # Last resort - default server
                    try:
                        print("Attempt 3: Creating default server...")
                        self.server = pyo.Server()
                        self.server.boot()
                        self.server.start()
                        print("Default server started")
                    except Exception as e:
                        print(f"Default server creation failed: {e}")
                        self.server = None
                        raise Exception("Could not create audio server")
            
            # 5. Verify server is working properly
            if not hasattr(self.server, 'getIsStarted') or not self.server.getIsStarted():
                raise Exception("Server failed to start properly")
                
            print("Audio server successfully restarted")
                
            # 6. Create a new particle
            try:
                print("Creating new particle...")
                self.particle = Particle(self.server)
                if not self.particle.initialized:
                    print("Warning: Particle not initialized properly")
                else:
                    print("Particle initialized successfully")
            except Exception as e:
                print(f"Error creating particle: {e}")
                self.particle = None
                raise Exception("Failed to create particle")
            
            # 7. Make sure the UI knows which oscillators to use
            try:
                osc_names = list(self.particle.oscillators.keys())
                print(f"Available oscillators: {osc_names}")
                
                # Reset the UI
                self.reset_ui_for_new_server()
                
                # Connect signals
                self.connect_midi_to_particle()
                self.connect_bypass_signals()
                
            except Exception as e:
                print(f"Error updating UI: {e}")
            
            # 8. Get the actual settings that were applied
            actual_device = device_index  # Default fallback
            try:
                if hasattr(self.server, 'getOutputDevice'):
                    actual_device = self.server.getOutputDevice()
            except Exception as e:
                print(f"Could not get actual device: {e}")
                
            try:
                actual_sr = self.server.getSamplingRate()
            except:
                actual_sr = sample_rate
                
            try:
                actual_bs = self.server.getBufferSize()
            except:
                actual_bs = buffer_size
                
            try:
                actual_nchnls = self.server.getNchnls()
            except:
                actual_nchnls = nchnls
            
            print(f"Actual settings: Device={actual_device}, SR={actual_sr}, BS={actual_bs}, Channels={actual_nchnls}")
            
            # 9. Test the audio channels
            try:
                self.test_audio_channels(actual_nchnls)
            except Exception as e:
                print(f"Error testing audio channels: {e}")
            
            # 10. Update the UI status
            try:
                self.update_audio_device_status()
            except Exception as e:
                print(f"Error updating device status: {e}")
            
            # 11. Show success message
            QMessageBox.information(self, "Audio Settings", 
                f"Audio settings applied successfully.\n\nDevice: {device_name}\nSample Rate: {actual_sr} Hz\nBuffer Size: {actual_bs}\nChannels: {actual_nchnls}")
                
        except Exception as e:
            QMessageBox.critical(self, "Audio Error", 
                f"Error applying audio settings: {e}\n\nThe synthesizer may not produce sound correctly.")
            
    def reset_ui_for_new_server(self):
        """Reset the UI when switching to a new server"""
        try:
            # Remove all tabs except the first one (Global tab)
            while self.tabs.count() > 1:
                self.tabs.removeTab(1)
                
            # Create new oscillator UIs if server is working
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
                    
                    print("Oscillator UI tabs created successfully")
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
        except Exception as e:
            print(f"Error resetting UI: {e}")
    
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
            num_channels = 2  # Default to stereo
        
        # Create a message box to show during the test
        msg = QMessageBox(self)
        msg.setWindowTitle("Audio Channel Test")
        msg.setText(f"Testing {num_channels} audio channels...")
        msg.setStandardButtons(QMessageBox.NoButton)
        
        # Get the current audio device info
        device_name = "Default"
        try:
            device_id = self.server.getOutputDevice()
            device_info = pyo.pa_get_output_devices()
            if device_id in device_info:
                device_name = device_info[device_id]
            msg.setInformativeText(f"Device: {device_name}\nChannels: {num_channels}\n\nListen for test tones on each channel.")
        except Exception as e:
            msg.setInformativeText(f"Unknown device\n\nListen for test tones on each channel.")
        
        # Show the message box without blocking
        msg.show()
        
        # Schedule the test to run after the UI has updated
        QTimer.singleShot(100, lambda: self._run_channel_test(num_channels, msg))
    
    def _run_channel_test(self, num_channels, msg_box):
        """Run the actual channel test and update the message box"""
        if not self.server or not self.server.getIsStarted():
            msg_box.done(0)  # Close the message box
            return
        
        # Get device info for logging
        device_name = "Default"
        try:
            device_id = self.server.getOutputDevice()
            device_info = pyo.pa_get_output_devices()
            if device_id in device_info:
                device_name = device_info[device_id]
            print(f"Test output device: {device_name} (ID: {device_id})")
        except:
            pass
            
        # Create a unique test signal for each channel with different frequencies
        # This makes it easier to tell which channel is which by ear
        base_freq = 440  # A4
        test_freqs = [
            base_freq,           # Channel 0 (Front Left): A4 (440 Hz)
            base_freq * 1.25,    # Channel 1 (Front Right): E5 (550 Hz)
            base_freq * 1.5,     # Channel 2 (Rear Left): A5 (660 Hz)
            base_freq * 1.75     # Channel 3 (Rear Right): E6 (770 Hz)
        ]
        
        channel_names = [
            "Front Left",
            "Front Right",
            "Rear Left",
            "Rear Right"
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
    
    def test_audio_channels(self, num_channels):
        """Test each audio channel individually with a sine tone (non-UI version)"""
        if not self.server or not self.server.getIsStarted():
            return
            
        print(f"Testing {num_channels} audio channels...")
        
        device_name = "Default"
        try:
            device_id = self.server.getOutputDevice()
            device_info = pyo.pa_get_output_devices()
            if device_id in device_info:
                device_name = device_info[device_id]
            print(f"Test output device: {device_name} (ID: {device_id})")
        except:
            pass
        
        # Create a more direct test tone for each channel
        duration = 0.3  # seconds per channel
        
        # Create a single oscillator we'll route to different channels
        test_sine = pyo.Sine(freq=440, mul=0.3)
        
        # Play on each channel sequentially
        for channel in range(num_channels):
            try:
                # Create message for user
                print(f"Testing channel {channel} on device '{device_name}'...")
                
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
                time.sleep(0.1)  # Small gap between tones
                
                # Clean up
                output.stop()
            except Exception as e:
                print(f"Error testing channel {channel}: {e}")
        
        # Clean up
        test_sine.stop()
        print("Channel test complete")
                
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
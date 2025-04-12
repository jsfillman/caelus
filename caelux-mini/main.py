import pyo
import mido
import random
import atexit
import sys
import time
import yaml

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

# Simple audio setup functions copied from Octolux
def select_audio_device():
    print("=== AUDIO DEVICES ===")
    pyo.pa_list_devices()
    return int(input("Select audio output device index: "))

def select_num_channels():
    return int(input("Number of audio output channels (e.g. 2): "))

def select_midi_device():
    print("\n=== MIDI INPUT DEVICES ===")
    inputs = mido.get_input_names()
    for i, name in enumerate(inputs):
        print(f"{i}: {name}")
    index = int(input("Select MIDI input port index: "))
    return inputs[index]

def start_server(audio_index, nchnls=2):
    # Simplified server startup like Octolux
    s = pyo.Server(nchnls=nchnls)
    s.setOutputDevice(audio_index)
    s.boot()
    s.start()
    return s

class MainWindow(QWidget):
    def __init__(self, server, midi_port=None):
        super().__init__()
        self.setWindowTitle("Caelux Mini")
        
        # Store the server reference and ensure it's running
        self.server = server
        if self.server and not self.server.getIsStarted():
            print("Starting audio server from MainWindow init")
            self.server.start()
        
        # Initialize particle
        self.particle = None
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
        
        # Let the GUI handle MIDI selection - don't connect to port here
        # If a port was provided, we'll connect to it, but normally we'll use the GUI selection
        if midi_port:
            print(f"Connecting to provided MIDI port: {midi_port}")
            self.midi_handler.open_port(midi_port)
        
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
        
        print("\n=== CONNECTING MIDI SIGNALS ===")
        
        # ALWAYS connect note on/off to our handler methods first
        try:
            # Reset all connections first
            try:
                self.midi_handler.note_on_signal.disconnect()
                self.midi_handler.note_off_signal.disconnect()
                self.midi_handler.pitch_bend_signal.disconnect()
                print("Disconnected existing MIDI signals")
            except:
                pass
            
            # Connect to our local handlers (these will generate console output)
            self.midi_handler.note_on_signal.connect(self.handle_note_on)
            print("Connected MIDI note ON signal to handler")
            
            # Create a basic note_off handler
            def handle_note_off(note):
                note_name = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"][note % 12]
                octave = note // 12 - 1
                print(f"🎹 MIDI NOTE OFF: {note_name}{octave} (note={note})")
                
                # Try to propagate to particle
                if hasattr(self, 'particle') and self.particle and hasattr(self.particle, 'note_off'):
                    try:
                        self.particle.note_off(note)
                        print(f"Note-off successfully triggered for {note_name}{octave}")
                    except Exception as e:
                        print(f"Error in particle.note_off: {e}")
            
            self.midi_handler.note_off_signal.connect(handle_note_off)
            print("Connected MIDI note OFF signal to handler")
            
            # If particle is initialized, also connect pitch bend
            if hasattr(self, 'particle') and self.particle and hasattr(self.particle, 'initialized') and self.particle.initialized:
                def handle_pitch_bend(value):
                    print(f"MIDI Pitch Bend: {value:.2f}")
                    if hasattr(self.particle, 'pitch_bend'):
                        try:
                            self.particle.pitch_bend(value)
                        except Exception as e:
                            print(f"Error in particle.pitch_bend: {e}")
                
                self.midi_handler.pitch_bend_signal.connect(handle_pitch_bend)
                print("Connected MIDI pitch bend signal to handler")
                
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
        # Create highly visible console output for MIDI note event
        note_name = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"][note % 12]
        octave = note // 12 - 1
        print("\n" + "="*50)
        print(f"🎹 MIDI NOTE ON: {note_name}{octave} (note={note}, velocity={velocity})")
        print("="*50 + "\n")
        
        # Always create a direct test tone for audible feedback
        try:
            freq = pyo.midiToHz(note)
            
            # Create a simple tone that bypasses all complex routing
            print(f"Playing direct test tone at {freq:.1f}Hz")
            test_tone = pyo.Sine(freq=freq, mul=velocity/127.0 * 0.5).out()
            
            # Auto-release after 1 second
            def release_tone():
                if hasattr(test_tone, 'stop'):
                    test_tone.stop()
                    print(f"Stopped test tone for note {note_name}{octave}")
            
            release_timer = QTimer()
            release_timer.setSingleShot(True)
            release_timer.timeout.connect(release_tone)
            release_timer.start(1000)  # 1 second note
        except Exception as e:
            print(f"Error creating direct test tone: {e}")
        
        # Check if particle exists and is initialized
        if not hasattr(self, 'particle') or not self.particle or not hasattr(self.particle, 'note_on'):
            print("Cannot trigger note in particle: particle not initialized")
            return
            
        # Create a dictionary of UI references for each oscillator
        ui_dict = {
            "OP1": self.op1_ui if hasattr(self, 'op1_ui') else None,
            "CAR1": self.car1_ui if hasattr(self, 'car1_ui') else None,
            "CAR2": self.car2_ui if hasattr(self, 'car2_ui') else None
        }
        
        # Try to trigger the normal synth engine
        try:
            # Double-check the server is running
            if self.server and not self.server.getIsStarted():
                print("Restarting audio server before triggering note")
                self.server.start()
            
            # Trigger note-on on the particle with UI references
            print(f"Triggering particle.note_on with note={note_name}{octave}")
            self.particle.note_on(note, velocity, ui_dict)
            print("Note successfully triggered on particle engine")
        except Exception as e:
            print(f"Error triggering note on particle: {e}")
    
    def init_audio_server(self):
        """Initialize audio server with default settings - simplified version"""
        try:
            print("\nINITIALIZING AUDIO SERVER:")
            
            # Check for saved audio settings file
            settings_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio_settings.yaml")
            saved_device = None
            nchnls = 2  # Default
            
            if os.path.exists(settings_file):
                try:
                    with open(settings_file, 'r') as f:
                        settings = yaml.safe_load(f)
                        if settings and 'device_index' in settings:
                            saved_device = settings['device_index']
                            nchnls = settings.get('num_channels', 2)
                            print(f"Found saved audio settings: device={saved_device}, channels={nchnls}")
                except Exception as e:
                    print(f"Error loading saved audio settings: {e}")
            
            # Simple server creation
            print("Creating audio server...")
            self.server = pyo.Server(nchnls=nchnls)
            print(f"Created server with {nchnls} channels")
            
            # Boot the server
            print("Booting the server...")
            self.server.boot()
            print("Server booted successfully")
            
            # Set device if we found saved settings
            if saved_device is not None:
                print(f"Setting output device to saved setting: {saved_device}")
                try:
                    # Try to set the device before starting
                    if hasattr(self.server, 'setOutputDevice'):
                        self.server.setOutputDevice(saved_device)
                        print(f"Successfully set output device to {saved_device}")
                except Exception as e:
                    print(f"Could not set saved device: {e}")
            
            # Start the server
            print("Starting the server...")
            self.server.start()
            print("Audio server started successfully")
            
            # Print audio server status
            print(f"Audio server is running: {self.server.getIsStarted()}")
            
            # Get channel count safely 
            try:
                num_channels = self.server.getNchnls()
                print(f"Audio server number of channels: {num_channels}")
            except:
                num_channels = nchnls
                print(f"Using default channel count: {num_channels}")
                
            # Test each channel
            print("Testing initial audio setup:")
            self.test_audio_channels(num_channels)
                
        except Exception as e:
            print(f"Error initializing audio server: {e}")
            QMessageBox.warning(self, "Audio Error", 
                f"Could not start audio server: {e}\n\nThe synthesizer will not produce sound.")
            self.server = None
    
    def create_global_tab(self):
        """Create the Global settings tab with MIDI selection only"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Audio Output notification - informational only
        audio_group = QGroupBox("Audio Output")
        audio_layout = QVBoxLayout()
        
        # Simple informational label with safely accessed properties
        try:
            sample_rate = self.server.getSamplingRate() if self.server else 'unknown'
            channels = self.server.getNchnls() if self.server else 'unknown'
            
            # Different pyo versions have different ways to get the current device
            device = 'unknown'
            try:
                # Try modern API
                device = self.server.getOutputDevice() if self.server else 'unknown'
            except AttributeError:
                # Fallback - just use the startup-selected device
                device = "selected at startup"
                
            self.audio_device_status = QLabel(f"Audio output device selected at startup. Current settings:\n"
                                           f"- Device: {device}\n"
                                           f"- Sample Rate: {sample_rate} Hz\n"
                                           f"- Channels: {channels}")
        except Exception:
            # Simplest fallback
            self.audio_device_status = QLabel("Audio output device selected at startup.")
        
        self.audio_device_status.setStyleSheet("color: #666; font-style: italic;")
        audio_layout.addWidget(self.audio_device_status)
        
        # Info label about changing audio
        restart_label = QLabel("To change audio device, restart the application.")
        restart_label.setStyleSheet("color: #666; font-style: italic;")
        audio_layout.addWidget(restart_label)
        
        # Add channel test button only
        self.test_channel_button = QPushButton("Test Audio")
        self.test_channel_button.clicked.connect(self.test_audio)
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
        """Change the MIDI input device with improved error handling"""
        if index < 0:
            return
        
        # Get the selected device name directly from dropdown
        selected_device = self.midi_devices.currentText()
        
        # Only proceed if it's a valid device name (not a placeholder message)
        if selected_device in ["No MIDI devices detected", "Error listing MIDI devices"]:
            return
        
        # Open the selected device in the MIDI handler
        try:
            # If we have an existing handler, just close and reopen the port
            if hasattr(self, 'midi_handler') and self.midi_handler:
                print(f"Changing MIDI device to: {selected_device}")
                # Close the current port
                self.midi_handler.close_port()
                
                # Open the new port (existing handler)
                success = self.midi_handler.open_port(selected_device)
                if success:
                    print(f"Connected to MIDI device: {selected_device}")
                else:
                    print(f"Could not connect to MIDI device: {selected_device}")
                    # Don't show an error dialog - just log it
            else:
                # Create a new MIDI handler
                print(f"Creating new MIDI handler for device: {selected_device}")
                self.midi_handler = MidiHandler()
                
                # Connect signals
                self.connect_midi_to_particle()
                
                # Open the port
                success = self.midi_handler.open_port(selected_device)
                if success:
                    print(f"Connected to MIDI device: {selected_device}")
                else:
                    print(f"Could not connect to MIDI device: {selected_device}")
        except Exception as e:
            print(f"MIDI connection error details: {e}")
            # Don't show error dialog - it's disruptive and not critical
            # Just try to reconnect to first available device
            self.refresh_midi_devices()
    
    def test_audio(self):
        """Simple audio test function using direct sine output"""
        if not hasattr(self, 'server') or not self.server:
            QMessageBox.warning(self, "Audio Test", "Audio server is not available")
            return
        
        try:
            # Use direct sine output to avoid mixer compatibility issues
            tones = []
            
            # Play a simple C major chord - one tone at a time with delays
            def play_c():
                # C4
                tone = pyo.Sine(freq=261.63, mul=0.3).out()
                tones.append(tone)
                QTimer.singleShot(750, play_e)  # Play E after 0.75 seconds
                
            def play_e():
                # E4
                tone = pyo.Sine(freq=329.63, mul=0.3).out()
                tones.append(tone)
                QTimer.singleShot(750, play_g)  # Play G after 0.75 seconds
                
            def play_g():
                # G4
                tone = pyo.Sine(freq=392.00, mul=0.3).out()
                tones.append(tone)
                QTimer.singleShot(750, stop_all)  # Stop all after 0.75 seconds
                
            def stop_all():
                for tone in tones:
                    tone.stop()
            
            # Start the sequence
            play_c()
            
            # Show message
            QMessageBox.information(self, "Audio Test", "Playing C-E-G arpeggio (notes will play one at a time)")
        
        except Exception as e:
            QMessageBox.warning(self, "Audio Test Error", f"Error testing audio: {e}")
            
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


def simple_test_tone(server, frequency=440, duration=1.0):
    """Play a simple test tone"""
    print(f"Testing with {frequency}Hz tone")
    tone = pyo.Sine(freq=frequency, mul=0.3).out()
    time.sleep(duration)
    tone.stop()
    print("Test tone complete")

if __name__ == "__main__":
    # === SETUP === (Only prompt for audio device)
    audio_index = select_audio_device()
    nchnls = select_num_channels()  
    
    # Don't select MIDI port from CLI - let the GUI handle it
    midi_port = None  # Will be selected in the GUI
    
    # Start the server with selected settings
    print("Starting audio server...")
    server = start_server(audio_index, nchnls)
    print(f"Server started successfully with {nchnls} channels")
    
    # Launch the Qt application
    print("Launching UI...")
    app = QApplication(sys.argv)
    win = MainWindow(server, midi_port)
    win.show()
    
    # Run the application
    sys.exit(app.exec_())
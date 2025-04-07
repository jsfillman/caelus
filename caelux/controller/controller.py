# controller.py
import mido
from pythonosc.udp_client import SimpleUDPClient
from pythonosc.osc_server import ThreadingOSCUDPServer
from pythonosc.dispatcher import Dispatcher
import threading
import time
import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QSlider, QVBoxLayout, 
                           QHBoxLayout, QLabel, QWidget, QGroupBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeyEvent

# Audio playback
from pyo import *

class CaeluxController:
    def __init__(self, worker_ip="127.0.0.1", worker_port=9004, listen_port=9003):
        # OSC client to send messages to worker
        self.osc_client = SimpleUDPClient(worker_ip, worker_port)
        
        # Save the port we'll listen on
        self.listen_port = listen_port
        
        # Start audio server for playback
        self.server = Server(nchnls=2).boot()
        self.server.start()
        
        # Audio input stream (from OSC) - we'll just use a silent generator for now
        self.audio_input = Sig(0, mul=0)
        self.audio_input.out()
        
        # Setup OSC receiver to get audio from worker
        self.setup_osc_receiver()
        
        # MIDI state
        self.current_note = None
        
        # Start MIDI input handling
        self.midi_thread = threading.Thread(target=self.midi_loop, daemon=True)
        self.midi_thread.start()
        
        print(f"Caelux controller initialized - listening on port {self.listen_port}, sending to {worker_port}")
    
    def setup_osc_receiver(self):
        """Set up OSC server to receive messages from worker"""
        dispatcher = Dispatcher()
        dispatcher.map("/audio", self.handle_audio)
        
        # Start OSC server in a separate thread
        # Use the listen_port parameter to specify where to listen
        self.osc_server = ThreadingOSCUDPServer(("127.0.0.1", self.listen_port), dispatcher)
        threading.Thread(target=self.osc_server.serve_forever, daemon=True).start()
    
    def handle_audio(self, address, *args):
        """Handle incoming audio data from worker"""
        # In a real implementation, this would receive and play audio
        # For now, we'll just print a message
        print(f"Received audio data from worker: {len(args)} samples")
    
    def midi_loop(self):
        """Handle MIDI input with preference for Xkey"""
        try:
            available_ports = mido.get_input_names()
            if not available_ports:
                print("No MIDI devices found")
                return
            
            # Look for Xkey device first
            port_name = None
            for name in available_ports:
                print(f"Found MIDI device: {name}")
                if "Xkey" in name:
                    port_name = name
                    break
            
            # If no Xkey found, use the first available device
            if not port_name:
                port_name = available_ports[0]
            
            print(f"Connecting to MIDI device: {port_name}")
            
            with mido.open_input(port_name) as port:
                for msg in port:
                    self.handle_midi_message(msg)
        except Exception as e:
            print(f"Error with MIDI: {e}")
    
    def handle_midi_message(self, msg):
        """Process MIDI messages and forward to worker"""
        print(f"CONTROLLER: Received MIDI message: {msg}")
        
        if msg.type == 'note_on' and msg.velocity > 0:
            # Convert MIDI note to frequency (A4 = 69 = 440Hz)
            freq = 440.0 * (2 ** ((msg.note - 69) / 12))
            vel = msg.velocity / 127.0
            
            # Send note_on to worker
            print(f"CONTROLLER: Sending note ON to worker: freq={freq}, vel={vel}")
            self.osc_client.send_message("/note", [freq, vel])
            self.current_note = msg.note
            
        elif msg.type in ['note_off', 'note_on'] and msg.velocity == 0:
            if msg.note == self.current_note:
                # Send note_off to worker
                print("CONTROLLER: Sending note OFF to worker")
                self.osc_client.send_message("/note", [0, 0])
                self.current_note = None
                
        elif msg.type == 'polytouch':
            # Only process polytouch for currently playing note
            if msg.note == self.current_note:
                # Normalize value to 0-1 range
                touch_val = msg.value / 127.0
                print(f"CONTROLLER: Sending polytouch: {touch_val:.2f}")
                self.osc_client.send_message("/touch", [touch_val])
    
    def simulate_note_on(self, note=60, velocity=100):
        """Simulate a MIDI note for testing without a MIDI device"""
        freq = 440.0 * (2 ** ((note - 69) / 12))
        vel = velocity / 127.0
        print(f"CONTROLLER: Simulating note ON: {note} (freq={freq:.1f}, vel={vel:.2f})")
        self.osc_client.send_message("/note", [freq, vel])
        self.current_note = note

    def simulate_note_off(self):
        """Simulate a MIDI note off for testing"""
        if self.current_note is not None:
            print(f"CONTROLLER: Simulating note OFF: {self.current_note}")
            self.osc_client.send_message("/note", [0, 0])
            self.current_note = None
    
    def set_adsr(self, attack, decay, sustain, release):
        """Send ADSR parameters to worker"""
        self.osc_client.send_message("/adsr", [attack, decay, sustain, release])


class ControllerGUI(QMainWindow):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        
        # Set up the main window
        self.setWindowTitle("Caelux Controller")
        self.setGeometry(100, 100, 400, 300)
        
        # Main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        
        # ADSR controls
        adsr_group = QGroupBox("ADSR Envelope")
        adsr_layout = QHBoxLayout()
        
        # Attack slider
        attack_layout = QVBoxLayout()
        self.attack_slider = QSlider(Qt.Vertical)
        self.attack_slider.setRange(1, 1000)  # 1ms to 1000ms
        self.attack_slider.setValue(10)  # Default 10ms
        self.attack_slider.valueChanged.connect(self.update_adsr)
        attack_layout.addWidget(self.attack_slider)
        attack_layout.addWidget(QLabel("Attack"))
        adsr_layout.addLayout(attack_layout)
        
        # Decay slider
        decay_layout = QVBoxLayout()
        self.decay_slider = QSlider(Qt.Vertical)
        self.decay_slider.setRange(1, 1000)  # 1ms to 1000ms
        self.decay_slider.setValue(100)  # Default 100ms
        self.decay_slider.valueChanged.connect(self.update_adsr)
        decay_layout.addWidget(self.decay_slider)
        decay_layout.addWidget(QLabel("Decay"))
        adsr_layout.addLayout(decay_layout)
        
        # Sustain slider
        sustain_layout = QVBoxLayout()
        self.sustain_slider = QSlider(Qt.Vertical)
        self.sustain_slider.setRange(0, 100)  # 0% to 100%
        self.sustain_slider.setValue(70)  # Default 70%
        self.sustain_slider.valueChanged.connect(self.update_adsr)
        sustain_layout.addWidget(self.sustain_slider)
        sustain_layout.addWidget(QLabel("Sustain"))
        adsr_layout.addLayout(sustain_layout)
        
        # Release slider
        release_layout = QVBoxLayout()
        self.release_slider = QSlider(Qt.Vertical)
        self.release_slider.setRange(1, 1000)  # 1ms to 1000ms
        self.release_slider.setValue(500)  # Default 500ms
        self.release_slider.valueChanged.connect(self.update_adsr)
        release_layout.addWidget(self.release_slider)
        release_layout.addWidget(QLabel("Release"))
        adsr_layout.addLayout(release_layout)
        
        adsr_group.setLayout(adsr_layout)
        main_layout.addWidget(adsr_group)
        
        # Status display and keyboard instructions
        self.status_label = QLabel("Ready - Press SPACE to play a note, S to stop")
        main_layout.addWidget(self.status_label)
        
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        
        # Initial ADSR update
        self.update_adsr()
    
    def update_adsr(self):
        """Send ADSR values to the controller"""
        attack = self.attack_slider.value() / 1000.0  # Convert to seconds
        decay = self.decay_slider.value() / 1000.0
        sustain = self.sustain_slider.value() / 100.0  # Convert to 0-1 range
        release = self.release_slider.value() / 1000.0
        
        self.controller.set_adsr(attack, decay, sustain, release)
        self.status_label.setText(f"ADSR: A={attack:.3f}s, D={decay:.3f}s, S={sustain:.2f}, R={release:.3f}s")
    
    def keyPressEvent(self, event):
        """Handle keyboard events for testing"""
        key = event.key()
        
        # Play middle C when spacebar is pressed
        if key == Qt.Key_Space:
            self.controller.simulate_note_on(60, 100)  # Middle C at moderate velocity
            self.status_label.setText("Playing note: 60 (Middle C)")
        
        # Stop note when 'S' is pressed
        elif key == Qt.Key_S:
            self.controller.simulate_note_off()
            self.status_label.setText("Note released")


# Main entry point
if __name__ == "__main__":
    try:
        # Controller listens on port 9003, sends to worker on port 9004
        app = QApplication(sys.argv)
        controller = CaeluxController(worker_port=9004, listen_port=9003)
        gui = ControllerGUI(controller)
        gui.show()
        sys.exit(app.exec_())
    except Exception as e:
        print(f"Error in main: {e}")
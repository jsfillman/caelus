# worker.py
from pyo import *
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient
import threading
import time
import numpy as np

class CaeluxWorker:
    def __init__(self, controller_ip="127.0.0.1", controller_port=9003, listen_port=9004):
        # Initialize pyo audio server 
        self.server = Server().boot()
        self.server.start()
        
        # OSC client to send audio data back to controller
        self.osc_client = SimpleUDPClient(controller_ip, controller_port)
        
        # Save the port we'll listen on
        self.listen_port = listen_port
        
        # Set up the synthesis engine
        self.setup_synth()
        
        # Set up OSC server to receive control messages
        self.setup_osc_server()
        
        print(f"Caelux worker initialized and ready - listening on port {self.listen_port}")
    
    def setup_synth(self):
        """Set up the basic FM synthesis engine"""
        # Basic FM synth with carrier and one modulator
        self.pitch = Sig(440.0)        # Base frequency
        self.velocity = Sig(0.0)       # MIDI velocity (0-1)
        self.aftertouch = Sig(0.0)     # Aftertouch value (0-1)
        
        # Store base values for parameters that can be affected by aftertouch
        self.base_carrier_amp = 0.25   # Initial carrier amplitude
        
        # Modulator
        self.mod_ratio = Sig(2.0)      # Modulator/carrier frequency ratio
        self.mod_index = Sig(5.0)      # Modulation depth/index
        
        # ADSR envelope for modulator
        self.mod_env = Adsr(attack=0.01, decay=0.1, sustain=0.7, release=0.5, dur=0, mul=1.0)
        
        # Calculate modulator frequency and amplitude
        self.mod_freq = self.pitch * self.mod_ratio
        self.mod_amp = self.pitch * self.mod_index * self.mod_env
        
        # Create the modulator oscillator
        self.modulator = Sine(freq=self.mod_freq, mul=self.mod_amp)
        
        # Carrier envelope with amplitude affected by aftertouch
        self.carrier_env = Adsr(attack=0.01, decay=0.1, sustain=0.7, release=0.5, dur=0, mul=self.base_carrier_amp)
        
        # Create the carrier oscillator with FM from modulator
        # Scale amplitude based on velocity and aftertouch
        self.carrier = Sine(
            freq=self.pitch + self.modulator,
            mul=self.carrier_env * self.velocity * (0.5 + self.aftertouch * 2.0)
        )
        
        # Output
        self.output = self.carrier
        
        # Create a panner for stereo output
        self.panner = Pan(self.output, outs=2, pan=0.5).out()
        
        # Start a thread to periodically send audio back to controller
        self.audio_thread = threading.Thread(target=self.audio_sender_loop, daemon=True)
        self.audio_thread.start()
    
    def audio_sender_loop(self):
        """Periodically send audio data back to controller"""
        while True:
            # In a real implementation, we would send actual audio data
            # For now, just send a placeholder
            self.osc_client.send_message("/audio", [0.0] * 256)  # Send 256 silence samples
            time.sleep(0.1)  # 100ms intervals
    
    def setup_osc_server(self):
        """Set up OSC server to receive control messages from controller"""
        dispatcher = Dispatcher()
        dispatcher.map("/note", self.handle_note)
        dispatcher.map("/adsr", self.handle_adsr)
        dispatcher.map("/touch", self.handle_touch)  # Add polytouch handler
        
        # Start OSC server in a separate thread
        # Use the listen_port parameter to specify where to listen
        self.osc_server = ThreadingOSCUDPServer(("0.0.0.0", self.listen_port), dispatcher)
        threading.Thread(target=self.osc_server.serve_forever, daemon=True).start()
    
    def handle_note(self, address, *args):
        """Handle note on/off messages"""
        freq, vel = args
        
        print(f"WORKER: Received note message on {address}: freq={freq}, vel={vel}")
        
        if freq > 0:  # Note on
            self.pitch.value = freq
            self.velocity.value = vel
            self.mod_env.play()
            self.carrier_env.play()
            print(f"WORKER: Note ON: {freq:.1f} Hz, velocity: {vel:.2f}")
        else:  # Note off
            self.mod_env.stop()
            self.carrier_env.stop()
            print("WORKER: Note OFF")
    
    def handle_touch(self, address, *args):
        """Handle polytouch/aftertouch messages"""
        touch_val = args[0]
        
        print(f"WORKER: Received polytouch: {touch_val:.2f}")
        
        # Update aftertouch value to affect amplitude
        self.aftertouch.value = touch_val
        
        # With the way we've set up the carrier oscillator, the amplitude
        # will automatically update based on the aftertouch value
    
    def handle_adsr(self, address, *args):
        """Handle ADSR parameter changes"""
        attack, decay, sustain, release = args
        
        # Update both envelopes
        self.mod_env.attack = attack
        self.mod_env.decay = decay
        self.mod_env.sustain = sustain
        self.mod_env.release = release
        
        self.carrier_env.attack = attack
        self.carrier_env.decay = decay
        self.carrier_env.sustain = sustain
        self.carrier_env.release = release
        
        print(f"ADSR updated: A={attack:.3f}s, D={decay:.3f}s, S={sustain:.2f}, R={release:.3f}s")


# Main entry point
if __name__ == "__main__":
    try:
        # Worker listens on port 9004, sends to controller on port 9003
        worker = CaeluxWorker(controller_port=9003, listen_port=9004)
        
        # Keep the main thread running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Worker shutting down...")
    except Exception as e:
        print(f"Error: {e}")
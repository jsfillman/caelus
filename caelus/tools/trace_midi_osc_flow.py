#!/usr/bin/env python3
"""
Trace MIDI-OSC Flow

This script helps trace the flow of MIDI messages through the OSC system:
1. Sets up OSC monitors on key ports
2. Simulates MIDI input or monitors real MIDI input
3. Shows exactly where OSC messages are flowing (or not)
"""

import argparse
import sys
import os
import time
import threading
import signal
import subprocess
from datetime import datetime
from pythonosc import udp_client, dispatcher, osc_server

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

# Try to import from Caelus, but don't fail if not found
try:
    from lib.common.utils import LOG
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    LOG = logging.getLogger(__name__)

class OSCMonitor:
    """Monitor OSC traffic on a specific port"""
    
    def __init__(self, port, name):
        """Initialize with port to monitor"""
        self.port = port
        self.name = name
        self.server = None
        self.thread = None
        self.running = False
        self.message_count = 0
        
    def handle_any_message(self, address, *args):
        """Handler for any OSC message"""
        # Format arguments for display
        if len(args) == 0:
            args_formatted = "(no args)"
        elif len(args) == 1:
            args_formatted = str(args[0])
        else:
            args_formatted = str(args)
            
        # Get timestamp
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        
        # Increment counter
        self.message_count += 1
            
        # Print the message details
        print(f"[{timestamp}] {self.name} ({self.port}) | {address} = {args_formatted}")
        
    def start_monitoring(self):
        """Start monitoring all ports"""
        try:
            # Create a dispatcher
            disp = dispatcher.Dispatcher()
            disp.set_default_handler(self.handle_any_message)
            
            # Create server
            self.server = osc_server.ThreadingOSCUDPServer(('0.0.0.0', self.port), disp)
            self.running = True
            
            # Create and start thread
            self.thread = threading.Thread(
                target=self._server_thread, 
                daemon=True
            )
            self.thread.start()
            
            print(f"Monitoring OSC on {self.name} port {self.port}...")
            return True
            
        except Exception as e:
            print(f"Error starting server on port {self.port}: {e}")
            return False
    
    def _server_thread(self):
        """Thread function for server"""
        try:
            # Custom serve_forever that can be stopped
            while self.running:
                self.server.handle_request()
                
        except Exception as e:
            if self.running:  # Only show error if not shutting down
                print(f"Error in server thread for {self.name}: {e}")
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self.running = False
        
        # Close server
        if self.server:
            try:
                self.server.server_close()
            except:
                pass
                
        print(f"Stopped monitoring {self.name}.")

class MIDIMonitor:
    """Monitor MIDI input and generate OSC messages"""
    
    def __init__(self, midi_port=None, router_port=9000, router_host="127.0.0.1"):
        """Initialize with MIDI port to monitor"""
        self.midi_port = midi_port
        self.router_port = router_port
        self.router_host = router_host
        self.midi_process = None
        self.router_client = None
        self.running = False
        
    def start_monitoring(self):
        """Start monitoring MIDI input"""
        try:
            # Create OSC client for router
            self.router_client = udp_client.SimpleUDPClient(self.router_host, self.router_port)
            print(f"Created OSC client for router at {self.router_host}:{self.router_port}")
            
            if self.midi_port:
                # Use external MIDI input via mido
                try:
                    import mido
                    self.running = True
                    
                    # Start in a thread
                    self.thread = threading.Thread(
                        target=self._monitor_midi_thread,
                        daemon=True
                    )
                    self.thread.start()
                    
                    print(f"Monitoring MIDI input from port: {self.midi_port}")
                    return True
                except ImportError:
                    print("Error: mido not installed. Cannot monitor real MIDI.")
                    return False
            else:
                # No MIDI port specified, we'll simulate MIDI input
                print("No MIDI port specified. Will use simulated MIDI input.")
                return True
            
        except Exception as e:
            print(f"Error starting MIDI monitor: {e}")
            return False
    
    def _monitor_midi_thread(self):
        """Thread for monitoring MIDI input"""
        try:
            import mido
            
            # Open MIDI port
            with mido.open_input(self.midi_port) as midi_in:
                print(f"Opened MIDI port: {self.midi_port}")
                
                # Process MIDI messages
                while self.running:
                    # Wait for a message with timeout
                    for msg in midi_in.iter_pending():
                        self._handle_midi_message(msg)
                    time.sleep(0.001)
                    
        except Exception as e:
            if self.running:
                print(f"Error in MIDI monitoring thread: {e}")
    
    def _handle_midi_message(self, msg):
        """Handle a MIDI message and convert to OSC"""
        # Print the MIDI message
        print(f"MIDI: {msg}")
        
        # Convert to OSC
        if msg.type == 'note_on':
            if msg.velocity == 0:
                # Note-on with velocity 0 is note-off
                self.send_note_off(msg.note)
            else:
                # Regular note-on
                velocity = msg.velocity / 127.0
                self.send_note_on(msg.note, velocity)
        
        elif msg.type == 'note_off':
            self.send_note_off(msg.note)
            
        elif msg.type == 'control_change':
            # Handle specific CCs
            if msg.control == 64:  # Sustain pedal
                self.send_sustain(msg.value)
            else:
                self.send_cc(msg.control, msg.value)
                
        elif msg.type == 'pitchwheel':
            # Normalize to -1 to 1
            value = msg.pitch / 8192.0
            self.send_pitch_bend(value)
    
    def send_note_on(self, note, velocity):
        """Send note-on OSC message"""
        if self.router_client:
            print(f"Sending OSC note_on: note={note}, velocity={velocity:.2f}")
            self.router_client.send_message("/router/note_on", [note, velocity])
    
    def send_note_off(self, note):
        """Send note-off OSC message"""
        if self.router_client:
            print(f"Sending OSC note_off: note={note}")
            self.router_client.send_message("/router/note_off", [note])
    
    def send_cc(self, cc_num, value):
        """Send CC OSC message"""
        if self.router_client:
            print(f"Sending OSC CC: cc={cc_num}, value={value}")
            self.router_client.send_message("/router/cc", [cc_num, value])
    
    def send_sustain(self, value):
        """Send sustain OSC message"""
        if self.router_client:
            print(f"Sending OSC sustain: value={value}")
            self.router_client.send_message("/router/sustain", [value])
    
    def send_pitch_bend(self, value):
        """Send pitch bend OSC message"""
        if self.router_client:
            print(f"Sending OSC pitch_bend: value={value:.2f}")
            self.router_client.send_message("/router/pitch_bend", [value])
    
    def simulate_midi(self):
        """Simulate MIDI input with a pattern"""
        if not self.router_client:
            print("OSC client not set up. Cannot simulate MIDI.")
            return
            
        try:
            # Play a scale
            notes = [60, 62, 64, 65, 67, 69, 71, 72]
            
            print("\nSimulating MIDI note sequence...\n")
            
            for note in notes:
                # Note on
                self.send_note_on(note, 0.8)
                time.sleep(0.2)
                
                # Note off
                self.send_note_off(note)
                time.sleep(0.1)
                
            # Wait a moment
            time.sleep(0.5)
            
            # Now play a chord
            print("\nSimulating MIDI chord...\n")
            
            # C major chord
            self.send_note_on(60, 0.8)  # C
            time.sleep(0.05)
            self.send_note_on(64, 0.8)  # E
            time.sleep(0.05)
            self.send_note_on(67, 0.8)  # G
            time.sleep(1.0)
            
            # Turn off chord
            self.send_note_off(60)
            time.sleep(0.05)
            self.send_note_off(64)
            time.sleep(0.05)
            self.send_note_off(67)
            
            print("\nSimulation complete.\n")
            
        except Exception as e:
            print(f"Error in MIDI simulation: {e}")
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self.running = False
        print("Stopped MIDI monitoring.")

def get_midi_ports():
    """Get list of available MIDI ports"""
    try:
        import mido
        ports = mido.get_input_names()
        return ports
    except ImportError:
        print("Warning: mido not installed. Cannot list MIDI ports.")
        return []

def run_osc_trace():
    """Run the full OSC trace"""
    parser = argparse.ArgumentParser(description="Trace MIDI-OSC flow in Caelus")
    parser.add_argument("-m", "--midi-port", type=str, 
                       help="MIDI port to monitor (if not specified, will simulate MIDI)")
    parser.add_argument("-l", "--list-midi", action="store_true",
                       help="List available MIDI ports and exit")
    parser.add_argument("-r", "--router-port", type=int, default=9000,
                       help="Router OSC port (default: 9000)")
    parser.add_argument("-s", "--synth-port", type=int, default=5510,
                       help="Synth OSC port (default: 5510)")
    parser.add_argument("-n", "--synth-name", type=str, default="simple",
                       help="Synth name from voices.yaml (default: simple)")
    
    args = parser.parse_args()
    
    # List MIDI ports if requested
    if args.list_midi:
        ports = get_midi_ports()
        if ports:
            print("Available MIDI ports:")
            for i, port in enumerate(ports):
                print(f"  {i+1}: {port}")
        else:
            print("No MIDI ports found.")
        return 0
    
    # Create monitors
    router_monitor = OSCMonitor(args.router_port, "Router")
    synth_monitor = OSCMonitor(args.synth_port, "Synth")
    midi_monitor = MIDIMonitor(args.midi_port, args.router_port)
    
    # Variables for monitoring
    monitors = [router_monitor, synth_monitor]
    
    try:
        # Start all monitors
        print("Starting OSC monitors...")
        router_started = router_monitor.start_monitoring()
        synth_started = synth_monitor.start_monitoring()
        midi_started = midi_monitor.start_monitoring()
        
        # Check if at least router monitoring works
        if not router_started and not synth_started:
            print("Both router and synth ports are in use. Unable to monitor either.")
            print("This likely means Caelus is already running.")
            print("Try using 'netstat -an | grep 9000' and 'netstat -an | grep 5510' to confirm.")
            return 1
            
        # Continue even if one monitor fails - could be because the actual service is running there
        if not router_started:
            print("Warning: Router port monitoring failed, but will continue...")
            
        if not synth_started:
            print("Warning: Synth port monitoring failed, but will continue...")
            print("This is expected if the synth is already running.")
            
        if not midi_started:
            print("Error: MIDI monitoring failed. Cannot continue.")
            return 1
        
        # Wait for things to settle
        time.sleep(1)
        
        print("\n" + "=" * 50)
        print("MIDI-OSC TRACE STARTED")
        print("=" * 50)
        print(f"Router port: {args.router_port}")
        print(f"Synth port: {args.synth_port}")
        print(f"Synth name: {args.synth_name}")
        if args.midi_port:
            print(f"MIDI port: {args.midi_port}")
        else:
            print("Using simulated MIDI input")
            
        print("\nWaiting for MIDI messages...")
        print("(Press Ctrl+C to stop or wait for simulated sequence to complete)")
        print("-" * 50 + "\n")
        
        # If no MIDI port specified, simulate MIDI input
        if not args.midi_port:
            midi_monitor.simulate_midi()
            
            # After simulation, show summary
            time.sleep(1)
            print("\n" + "=" * 50)
            print("SIMULATION RESULTS")
            print("=" * 50)
            print(f"Router OSC messages received: {router_monitor.message_count}")
            print(f"Synth OSC messages received: {synth_monitor.message_count}")
            
            if router_monitor.message_count > 0 and synth_monitor.message_count == 0:
                print("\nDIAGNOSIS: Messages are reaching the router but not the synth.")
                print("Possible issues:")
                print("1. Voice allocation in the router is not working properly")
                print("2. The voice.py send_osc method isn't formatting paths correctly")
                print("3. The synth_name in voices.yaml doesn't match what the synth expects")
                print("4. The synth port in voices.yaml is incorrect")
                
                print("\nRecommended steps:")
                print(f"1. Check that voices.yaml has port={args.synth_port}")
                print(f"2. Use tools/play_note.py -p {args.synth_port} to test direct communication")
                print(f"3. Review the fix in lib/osc_bridge/voice.py for proper path formatting")
                
            elif router_monitor.message_count == 0:
                print("\nDIAGNOSIS: Messages are not reaching the router.")
                print("Possible issues:")
                print("1. MIDI to OSC conversion isn't working")
                print("2. The router port specified is incorrect")
                print("3. The router is not running")
                
                print("\nRecommended steps:")
                print(f"1. Check that the router is running and listening on port {args.router_port}")
                print(f"2. Use tools/debug_router.py to test direct router communication")
                
            elif router_monitor.message_count > 0 and synth_monitor.message_count > 0:
                print("\nDIAGNOSIS: Messages are flowing correctly through the system.")
                print("If you're still not hearing sound, the issue is likely with the audio backend.")
                
                print("\nRecommended steps:")
                print("1. Check the JACK server status with tools/check_audio_system.py")
                print("2. Ensure the synth process is correctly connected to the audio system")
            
            print("\nTracing complete.")
            return 0
        else:
            # Keep running until Ctrl+C if real MIDI port is specified
            while True:
                time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        # Stop all monitors
        for monitor in monitors:
            monitor.stop_monitoring()
        midi_monitor.stop_monitoring()
        
        # Show summary
        print("\n" + "=" * 50)
        print("TRACE RESULTS")
        print("=" * 50)
        
        if router_started:
            print(f"Router OSC messages received: {router_monitor.message_count}")
        else:
            print("Router monitoring not available (port in use)")
            
        if synth_started:
            print(f"Synth OSC messages received: {synth_monitor.message_count}")
        else:
            print("Synth monitoring not available (port in use)")
            
        # Additional diagnostic information
        print("\nPort Status Information:")
        # Check if router port is in use
        import subprocess
        try:
            # Different commands for different platforms
            if sys.platform == 'darwin':  # macOS
                result = subprocess.run(['lsof', '-i', f':{args.router_port}'], 
                                      capture_output=True, text=True)
                if result.stdout:
                    print(f"Router port {args.router_port} is in use by:")
                    print(result.stdout)
                else:
                    print(f"Router port {args.router_port} is not in use")
                    
                result = subprocess.run(['lsof', '-i', f':{args.synth_port}'], 
                                      capture_output=True, text=True)
                if result.stdout:
                    print(f"Synth port {args.synth_port} is in use by:")
                    print(result.stdout)
                else:
                    print(f"Synth port {args.synth_port} is not in use")
            else:  # Linux/Unix
                result = subprocess.run(['netstat', '-tln'], 
                                      capture_output=True, text=True)
                if str(args.router_port) in result.stdout:
                    print(f"Router port {args.router_port} is in use")
                else:
                    print(f"Router port {args.router_port} is not in use")
                    
                if str(args.synth_port) in result.stdout:
                    print(f"Synth port {args.synth_port} is in use")
                else:
                    print(f"Synth port {args.synth_port} is not in use")
        except Exception as e:
            print(f"Could not check port status: {e}")
    
    return 0

if __name__ == "__main__":
    sys.exit(run_osc_trace())
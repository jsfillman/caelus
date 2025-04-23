"""
MIDI Worker thread for processing MIDI messages
"""
import time
import mido
import threading
from lib.common.utils import LOG

class MidiWorker(threading.Thread):
    """Thread for processing MIDI input messages"""
    def __init__(self, port_name, midi_callback):
        super().__init__(daemon=True)
        self.port_name = port_name
        self.running = True
        self.midi_callback = midi_callback
        self.inport = None

    def run(self):
        try:
            LOG.info(f"Opening MIDI port: {self.port_name}")
            # Keep the port object as an instance variable
            self.inport = mido.open_input(self.port_name)
            LOG.info(f"MIDI port opened successfully: {self.port_name}")
            LOG.info("Waiting for MIDI messages... (play some notes)")
            
            # Main message processing loop
            while self.running:
                # Process all pending messages
                for msg in self.inport.iter_pending():
                    try:
                        self.midi_callback(msg)
                    except Exception as e:
                        LOG.error(f"Error processing MIDI message: {e}")
                # Brief sleep to prevent CPU hogging
                time.sleep(0.001)  # Use a shorter sleep time for better responsiveness
                
        except Exception as e:
            LOG.error(f"ERROR in MIDI thread: {e}")
            LOG.error("Available MIDI ports:", mido.get_input_names())
            import traceback
            traceback.print_exc()
        finally:
            # Always close the port when done
            if self.inport:
                LOG.info(f"Closing MIDI port: {self.port_name}")
                self.inport.close()

    def stop(self):
        """Stop the MIDI processing thread"""
        self.running = False
        # Give the thread a moment to clean up
        time.sleep(0.1)
        # Force close the port if it's still open
        if self.inport:
            try:
                self.inport.close()
            except Exception:
                pass 
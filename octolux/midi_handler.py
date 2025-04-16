# midi_handler.py
import mido
import threading
import time

# Flag to control MIDI loop
midi_running = True
midi_thread = None

def start_midi_listener(port_name, callback):
    global midi_running, midi_thread
    
    # Reset the running flag in case this is called multiple times
    midi_running = True
    
    def midi_loop():
        global midi_running
        
        try:
            with mido.open_input(port_name) as port:
                print(f"MIDI listening on: {port_name}")
                
                while midi_running:
                    # Non-blocking receive with timeout
                    try:
                        # Use get_message with timeout instead of iteration
                        for msg in port.iter_pending():
                            if not midi_running:
                                break
                                
                            if msg.type == "note_on" and msg.velocity > 0:
                                callback("note_on", msg.note, msg.velocity)
                            elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                                callback("note_off", msg.note, 0)
                            elif msg.type == "polytouch":
                                callback("polytouch", msg.note, msg.value)
                            elif msg.type == "aftertouch":
                                callback("aftertouch", None, msg.value)
                        
                        # Small sleep to prevent CPU hogging
                        time.sleep(0.001)
                        
                    except Exception as e:
                        print(f"Error processing MIDI message: {e}")
                        time.sleep(0.1)  # Sleep a bit longer on error
                
                print("MIDI thread exiting cleanly")
        except Exception as e:
            print(f"Error in MIDI thread: {e}")

    # Start the MIDI thread
    midi_thread = threading.Thread(target=midi_loop)
    midi_thread.daemon = True
    midi_thread.start()
    
    return midi_thread

def stop_midi_listener():
    """Safely stop the MIDI listening thread"""
    global midi_running, midi_thread
    
    print("Stopping MIDI listener...")
    midi_running = False
    
    # If thread exists and is running, wait for it to finish
    if midi_thread and midi_thread.is_alive():
        midi_thread.join(timeout=1.0)  # Wait up to 1 second
        if midi_thread.is_alive():
            print("Warning: MIDI thread did not terminate within timeout")
        else:
            print("MIDI thread successfully terminated")

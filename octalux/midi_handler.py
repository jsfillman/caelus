# midi_handler.py
import mido
import threading

def start_midi_listener(port_name, callback):
    def midi_loop():
        with mido.open_input(port_name) as port:
            print(f"MIDI listening on: {port_name}")
            for msg in port:
                if msg.type == "note_on" and msg.velocity > 0:
                    callback("note_on", msg.note, msg.velocity)
                elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                    callback("note_off", msg.note, 0)
                elif msg.type == "polytouch":
                    callback("polytouch", msg.note, msg.value)
                elif msg.type == "aftertouch":
                    callback("aftertouch", None, msg.value)

    thread = threading.Thread(target=midi_loop)
    thread.daemon = True
    thread.start()

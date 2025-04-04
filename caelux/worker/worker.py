# worker.py
from pyo import *
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer
import threading

# --- Pyo Synth Engine ---
s = Server().boot()
s.start()

table = HarmTable([1])
adsr = Adsr(attack=0.01, decay=0.1, sustain=0.7, release=0.5, dur=0, mul=1)
osc = Osc(table=table, freq=0, mul=adsr).out()

# --- OSC Handlers ---
def handle_note(addr, *args):
    freq, amp = args
    if freq > 0:
        osc.freq = freq
        adsr.mul = amp
        adsr.play()
    else:
        adsr.stop()

def handle_adsr(addr, *args):
    a, d, s_, r = args
    adsr.attack = a
    adsr.decay = d
    adsr.sustain = s_
    adsr.release = r
    print(f"Set ADSR: A={a:.3f}, D={d:.3f}, S={s_:.3f}, R={r:.3f}")

# --- OSC Setup ---
dispatcher = Dispatcher()
dispatcher.map("/note", handle_note)
dispatcher.map("/adsr", handle_adsr)

def start_osc_server():
    server = BlockingOSCUDPServer(("127.0.0.1", 9000), dispatcher)
    print("✅ OSC server running on port 9000...")
    server.serve_forever()

# Run OSC in background thread
threading.Thread(target=start_osc_server, daemon=True).start()

# Launch GUI
s.gui(locals())


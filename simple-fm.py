import mido
from threading import Thread
from pyo import *

# Boot the audio server with stereo output
s = Server(nchnls=2).boot()
s.start()

# === Control signals ===
pitch = Sig(440.0)
velocity = Sig(0.0)
aftertouch = Sig(0.0)

# === OPERATOR 1 (Modulator) ===
# Create controls with default values
op1_ratio = Sig(2.0)          # Operator1/carrier frequency ratio
op1_index = Sig(10.0)         # Modulation index (depth)
op1_freq_offset = Sig(0.0)    # Additional frequency offset in Hz

# Envelope for Operator 1
op1_env = Adsr(attack=0.01, decay=0.1, sustain=0.6, release=0.4, dur=1, mul=1.0)

# Ramp parameters for Operator 1
op1_freq_ramp_start = Sig(0.0)
op1_freq_ramp_end = Sig(0.0)
op1_freq_ramp_time = Sig(1.0)

op1_amp_ramp_start = Sig(1.0)
op1_amp_ramp_end = Sig(1.0)
op1_amp_ramp_time = Sig(1.0)

# Create the Linseg objects for Operator 1
op1_freq_ramp = Linseg([(0, 0), (1, 0)])
op1_amp_ramp = Linseg([(0, 1.0), (1, 1.0)])

# === OPERATOR 2 (Second Modulator) ===
# Create controls with default values
op2_ratio = Sig(1.5)          # Operator2/carrier frequency ratio
op2_index = Sig(8.0)          # Modulation index (depth)
op2_freq_offset = Sig(0.0)    # Additional frequency offset in Hz

# Envelope for Operator 2
op2_env = Adsr(attack=0.01, decay=0.1, sustain=0.6, release=0.4, dur=1, mul=1.0)

# Ramp parameters for Operator 2
op2_freq_ramp_start = Sig(0.0)
op2_freq_ramp_end = Sig(0.0)
op2_freq_ramp_time = Sig(1.0)

op2_amp_ramp_start = Sig(1.0)
op2_amp_ramp_end = Sig(1.0)
op2_amp_ramp_time = Sig(1.0)

# Create the Linseg objects for Operator 2
op2_freq_ramp = Linseg([(0, 0), (1, 0)])
op2_amp_ramp = Linseg([(0, 1.0), (1, 1.0)])

# === CARRIER ===
# Carrier ramp parameters
car_freq_ramp_start = Sig(0.0)
car_freq_ramp_end = Sig(0.0)
car_freq_ramp_time = Sig(1.0)

car_amp_ramp_start = Sig(1.0)
car_amp_ramp_end = Sig(1.0)
car_amp_ramp_time = Sig(1.0)

# Create the Linseg objects for Carrier
car_freq_ramp = Linseg([(0, 0), (1, 0)])
car_amp_ramp = Linseg([(0, 1.0), (1, 1.0)])

# Function to update all ramps
def update_ramps():
    # Update Operator 1 ramps
    op1_freq_time = max(0.01, op1_freq_ramp_time.get())
    op1_amp_time = max(0.01, op1_amp_ramp_time.get())
    
    op1_freq_ramp.setList([
        (0, op1_freq_ramp_start.get()), 
        (op1_freq_time, op1_freq_ramp_end.get())
    ])
    
    op1_amp_ramp.setList([
        (0, op1_amp_ramp_start.get()), 
        (op1_amp_time, op1_amp_ramp_end.get())
    ])
    
    # Update Operator 2 ramps
    op2_freq_time = max(0.01, op2_freq_ramp_time.get())
    op2_amp_time = max(0.01, op2_amp_ramp_time.get())
    
    op2_freq_ramp.setList([
        (0, op2_freq_ramp_start.get()), 
        (op2_freq_time, op2_freq_ramp_end.get())
    ])
    
    op2_amp_ramp.setList([
        (0, op2_amp_ramp_start.get()), 
        (op2_amp_time, op2_amp_ramp_end.get())
    ])
    
    # Update Carrier ramps
    car_freq_time = max(0.01, car_freq_ramp_time.get())
    car_amp_time = max(0.01, car_amp_ramp_time.get())
    
    car_freq_ramp.setList([
        (0, car_freq_ramp_start.get()), 
        (car_freq_time, car_freq_ramp_end.get())
    ])
    
    car_amp_ramp.setList([
        (0, car_amp_ramp_start.get()), 
        (car_amp_time, car_amp_ramp_end.get())
    ])

# Create triggers to update ramps when parameters change
param_trigger = Change(
    op1_freq_ramp_start + op1_freq_ramp_end + op1_freq_ramp_time + 
    op1_amp_ramp_start + op1_amp_ramp_end + op1_amp_ramp_time +
    op2_freq_ramp_start + op2_freq_ramp_end + op2_freq_ramp_time + 
    op2_amp_ramp_start + op2_amp_ramp_end + op2_amp_ramp_time +
    car_freq_ramp_start + car_freq_ramp_end + car_freq_ramp_time + 
    car_amp_ramp_start + car_amp_ramp_end + car_amp_ramp_time
).play()
param_updater = TrigFunc(param_trigger, update_ramps)

# === BUILD THE FM CHAIN (OPERATOR 1 -> OPERATOR 2 -> CARRIER) ===
# Operator 1 calculations
op1_freq = pitch * op1_ratio + op1_freq_offset + op1_freq_ramp * pitch
op1_amp = pitch * op1_index * op1_env * op1_amp_ramp
op1_osc = Sine(freq=op1_freq, mul=op1_amp)

# Operator 2 calculations (modulated by Operator 1)
op2_freq = pitch * op2_ratio + op2_freq_offset + op2_freq_ramp * pitch + op1_osc
op2_amp = pitch * op2_index * op2_env * op2_amp_ramp
op2_osc = Sine(freq=op2_freq, mul=op2_amp)

# Carrier calculations (modulated by Operator 2)
carrier_freq = pitch + op2_osc + car_freq_ramp * pitch
carrier_amp_env = Adsr(attack=0.01, decay=0.1, sustain=0.8, release=0.5, dur=1, mul=0.15)
carrier = Sine(
    freq=carrier_freq,
    mul=carrier_amp_env * velocity * (0.5 + aftertouch**2 * 2) * car_amp_ramp
)

# === STEREO OUTPUT WITH CENTER PANNING ===
panner = Pan(carrier, outs=2, pan=0.5)

# === AUDIO OUTPUT WITH LIMITER ===
limiter = Compress(
    input=panner,
    thresh=-12,
    ratio=20,
    risetime=0.001,
    falltime=0.1,
    lookahead=5,
    knee=0.5,
    outputAmp=False
)

final = limiter * 0.7
final.out()

# === MIDI handler ===
current_note = [None]

def midi_loop():
    port_name = None
    for name in mido.get_input_names():
        print("→", name)
        if "Xkey" in name:
            port_name = name
            break
    if not port_name:
        print("❌ Xkey not found. Using default.")
        port_name = mido.get_input_names()[0]

    print(f"🎹 Listening on: {port_name}")

    with mido.open_input(port_name) as port:
        for msg in port:
            if msg.type == 'note_on' and msg.velocity > 0:
                freq_val = 440.0 * (2 ** ((msg.note - 69) / 12))
                pitch.value = freq_val
                velocity.value = msg.velocity / 127
                
                # Play envelopes
                carrier_amp_env.play()
                op1_env.play()
                op2_env.play()
                
                # Force an update of the ramps with current values
                update_ramps()
                
                # Reset and play all ramps for each new note
                op1_freq_ramp.play()
                op1_amp_ramp.play()
                op2_freq_ramp.play()
                op2_amp_ramp.play()
                car_freq_ramp.play()
                car_amp_ramp.play()
                
                current_note[0] = msg.note
                
            elif msg.type in ['note_off', 'note_on'] and msg.velocity == 0:
                if msg.note == current_note[0]:
                    # Stop envelopes
                    carrier_amp_env.stop()
                    op1_env.stop()
                    op2_env.stop()
                    
            elif msg.type == 'polytouch':
                if msg.note == current_note[0]:
                    aftertouch.value = msg.value / 127

# === GUI CONTROLS ===
# Operator 1 controls
op1_ratio.ctrl(title="Op1 Ratio")
op1_index.ctrl(title="Op1 Index (modulation depth)")
op1_freq_offset.ctrl(title="Op1 Freq Offset (Hz)")
op1_env.ctrl(title="Op1 Envelope")
op1_freq_ramp_start.ctrl(title="Op1 Freq Ramp Start")
op1_freq_ramp_end.ctrl(title="Op1 Freq Ramp End")
op1_freq_ramp_time.ctrl(title="Op1 Freq Ramp Time (sec)")
op1_amp_ramp_start.ctrl(title="Op1 Amp Ramp Start")
op1_amp_ramp_end.ctrl(title="Op1 Amp Ramp End")
op1_amp_ramp_time.ctrl(title="Op1 Amp Ramp Time (sec)")

# Operator 2 controls
op2_ratio.ctrl(title="Op2 Ratio")
op2_index.ctrl(title="Op2 Index (modulation depth)")
op2_freq_offset.ctrl(title="Op2 Freq Offset (Hz)")
op2_env.ctrl(title="Op2 Envelope")
op2_freq_ramp_start.ctrl(title="Op2 Freq Ramp Start")
op2_freq_ramp_end.ctrl(title="Op2 Freq Ramp End")
op2_freq_ramp_time.ctrl(title="Op2 Freq Ramp Time (sec)")
op2_amp_ramp_start.ctrl(title="Op2 Amp Ramp Start")
op2_amp_ramp_end.ctrl(title="Op2 Amp Ramp End")
op2_amp_ramp_time.ctrl(title="Op2 Amp Ramp Time (sec)")

# Carrier controls
car_freq_ramp_start.ctrl(title="Carrier Freq Ramp Start")
car_freq_ramp_end.ctrl(title="Carrier Freq Ramp End")
car_freq_ramp_time.ctrl(title="Carrier Freq Ramp Time (sec)")
car_amp_ramp_start.ctrl(title="Carrier Amp Ramp Start")
car_amp_ramp_end.ctrl(title="Carrier Amp Ramp End")
car_amp_ramp_time.ctrl(title="Carrier Amp Ramp Time (sec)")
carrier_amp_env.ctrl(title="Carrier Amplitude Envelope")

# Run update_ramps once to initialize with starting values
update_ramps()

# Launch MIDI handler
Thread(target=midi_loop, daemon=True).start()

# GUI
s.gui(locals())
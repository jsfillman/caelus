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
# Create controls with default values for e-piano sound
op1_ratio = Sig(3.0)          # Higher ratio for bell-like quality
op1_index = Sig(1.0)          # Start with modest index, but allow higher values via slider
op1_freq_offset = Sig(0.0)    # No offset needed

# Envelope for Operator 1 - quick attack, longer decay, low sustain (bell-like)
op1_env = Adsr(attack=0.005, decay=1.5, sustain=0.1, release=0.8, dur=1, mul=1.0)

# Ramp parameters for Operator 1
op1_freq_ramp_start = Sig(0.0)
op1_freq_ramp_end = Sig(0.0)
op1_freq_ramp_time = Sig(1.0)

op1_amp_ramp_start = Sig(1.0)
op1_amp_ramp_end = Sig(0.5)  # Decay in modulation for classic DX e-piano character
op1_amp_ramp_time = Sig(1.2)

# Create the Linseg objects for Operator 1
op1_freq_ramp = Linseg([(0, 0), (1, 0)])
op1_amp_ramp = Linseg([(0, 1.0), (1, 0.5)])

# === OPERATOR 2 (Second Modulator) ===
# Create controls with default values
op2_ratio = Sig(1.0)          # 1:1 ratio with carrier for classic piano tone
op2_index = Sig(0.8)          # Start with modest index, but allow higher values via slider
op2_freq_offset = Sig(0.0)    # No offset

# Envelope for Operator 2 - fast attack, medium decay
op2_env = Adsr(attack=0.01, decay=0.8, sustain=0.4, release=0.6, dur=1, mul=1.0)

# Ramp parameters for Operator 2
op2_freq_ramp_start = Sig(0.0)
op2_freq_ramp_end = Sig(0.0)
op2_freq_ramp_time = Sig(1.0)

op2_amp_ramp_start = Sig(1.0)
op2_amp_ramp_end = Sig(0.7)  # Slight decay
op2_amp_ramp_time = Sig(0.9)

# Create the Linseg objects for Operator 2
op2_freq_ramp = Linseg([(0, 0), (1, 0)])
op2_amp_ramp = Linseg([(0, 1.0), (1, 0.7)])

# === CARRIER ===
# Carrier ramp parameters
car_freq_ramp_start = Sig(0.0)
car_freq_ramp_end = Sig(0.0)
car_freq_ramp_time = Sig(1.0)

car_amp_ramp_start = Sig(1.0)
car_amp_ramp_end = Sig(0.8)  # Slight decay for more natural piano sound
car_amp_ramp_time = Sig(1.5)

# Create the Linseg objects for Carrier
car_freq_ramp = Linseg([(0, 0), (1, 0)])
car_amp_ramp = Linseg([(0, 1.0), (1, 0.8)])

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
op1_base_freq = pitch * op1_ratio + op1_freq_offset
op1_freq = op1_base_freq + (op1_freq_ramp * pitch)
# Scale the modulation amount with pitch for consistent effect across keyboard
op1_amp = pitch * op1_index * op1_env * op1_amp_ramp
op1_osc = Sine(freq=op1_freq, mul=op1_amp)

# Operator 2 calculations
op2_base_freq = pitch * op2_ratio + op2_freq_offset
op2_freq = op2_base_freq + (op2_freq_ramp * pitch) + op1_osc
# Scale the modulation amount with pitch for consistent effect across keyboard
op2_amp = pitch * op2_index * op2_env * op2_amp_ramp
op2_osc = Sine(freq=op2_freq, mul=op2_amp)

# Carrier calculations
carrier_base_freq = pitch
carrier_freq = carrier_base_freq + (car_freq_ramp * pitch) + op2_osc
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

# === MIDI handler with last note priority ===
# Keep track of active notes in a list (ordered by time pressed)
active_notes = []

def play_note(note, velocity_val):
    freq_val = 440.0 * (2 ** ((note - 69) / 12))
    pitch.value = freq_val
    velocity.value = velocity_val / 127
    
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

def stop_note():
    # Stop envelopes
    carrier_amp_env.stop()
    op1_env.stop()
    op2_env.stop()

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
                # Add the new note to our active notes list
                if msg.note not in active_notes:
                    active_notes.append(msg.note)
                
                # Play the most recently pressed note (last in the list)
                play_note(active_notes[-1], msg.velocity)
                
            elif msg.type in ['note_off', 'note_on'] and msg.velocity == 0:
                # Remove the note from active notes
                if msg.note in active_notes:
                    active_notes.remove(msg.note)
                
                # If we still have active notes, play the most recent one
                if active_notes:
                    # Get the last pressed note still active
                    last_note = active_notes[-1]
                    play_note(last_note, 100)  # Use default velocity of 100
                else:
                    # No notes left, stop sound
                    stop_note()
                    
            elif msg.type == 'polytouch':
                # Apply aftertouch only if it's for the currently playing note
                if active_notes and msg.note == active_notes[-1]:
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
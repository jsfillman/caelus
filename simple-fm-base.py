import mido
from threading import Thread
from pyo import *

# Boot the audio server with stereo output
s = Server(nchnls=2).boot()
s.start()

# === Control signals ===
pitch = Sig(440.0)
velocity = Sig(0.0)
aftertouch = Sig(0.0)  # Optional

# === FIXED FM IMPLEMENTATION ===
# Create controls with default values that will make modulation clearly audible
fm_ratio = Sig(2.0)          # Modulator/carrier frequency ratio
fm_index = Sig(10.0)         # Modulation index (depth)
mod_freq_offset = Sig(0.0)   # Additional frequency offset in Hz

# Envelope for FM modulation - now applies to the index
mod_index_env = Adsr(attack=0.01, decay=0.1, sustain=0.6, release=0.4, dur=1, mul=1.0)

# === LINESEQ PARAMETERS FOR RAMPS ===
# Modulator frequency ramp parameters - much wider ranges for dramatic effects
mod_freq_ramp_start = Sig(0.0)     # Starting offset in Hz
mod_freq_ramp_end = Sig(0.0)       # Ending offset in Hz
mod_freq_ramp_time = Sig(1.0)      # Duration in seconds

# Modulator amplitude ramp parameters
mod_amp_ramp_start = Sig(1.0)      # Starting multiplier
mod_amp_ramp_end = Sig(1.0)        # Ending multiplier 
mod_amp_ramp_time = Sig(1.0)       # Duration in seconds

# Carrier frequency ramp parameters - much wider ranges for dramatic effects
car_freq_ramp_start = Sig(0.0)     # Starting offset in Hz
car_freq_ramp_end = Sig(0.0)       # Ending offset in Hz  
car_freq_ramp_time = Sig(1.0)      # Duration in seconds

# Carrier amplitude ramp parameters
car_amp_ramp_start = Sig(1.0)      # Starting multiplier
car_amp_ramp_end = Sig(1.0)        # Ending multiplier
car_amp_ramp_time = Sig(1.0)       # Duration in seconds

# Create the Linseg objects with initial values
mod_freq_ramp = Linseg([(0, 0), (1, 0)])
mod_amp_ramp = Linseg([(0, 1.0), (1, 1.0)])
car_freq_ramp = Linseg([(0, 0), (1, 0)])
car_amp_ramp = Linseg([(0, 1.0), (1, 1.0)])

# Function to update Linseg parameters when sliders change
def update_ramps():
    # Get current values
    mod_freq_start = mod_freq_ramp_start.get()
    mod_freq_end = mod_freq_ramp_end.get()
    mod_freq_time = mod_freq_ramp_time.get()
    
    mod_amp_start = mod_amp_ramp_start.get()
    mod_amp_end = mod_amp_ramp_end.get()
    mod_amp_time = mod_amp_ramp_time.get()
    
    car_freq_start = car_freq_ramp_start.get()
    car_freq_end = car_freq_ramp_end.get()
    car_freq_time = car_freq_ramp_time.get()
    
    car_amp_start = car_amp_ramp_start.get()
    car_amp_end = car_amp_ramp_end.get()
    car_amp_time = car_amp_ramp_time.get()
    
    # Ensure times are not zero
    mod_freq_time = max(0.01, mod_freq_time)
    mod_amp_time = max(0.01, mod_amp_time)
    car_freq_time = max(0.01, car_freq_time)
    car_amp_time = max(0.01, car_amp_time)
    
    # Update the Linseg objects
    mod_freq_ramp.setList([(0, mod_freq_start), (mod_freq_time, mod_freq_end)])
    mod_amp_ramp.setList([(0, mod_amp_start), (mod_amp_time, mod_amp_end)])
    car_freq_ramp.setList([(0, car_freq_start), (car_freq_time, car_freq_end)])
    car_amp_ramp.setList([(0, car_amp_start), (car_amp_time, car_amp_end)])
    
    print(f"Updated ramps:")
    print(f"Mod Freq: {mod_freq_start} to {mod_freq_end} in {mod_freq_time}s")
    print(f"Mod Amp: {mod_amp_start} to {mod_amp_end} in {mod_amp_time}s")
    print(f"Car Freq: {car_freq_start} to {car_freq_end} in {car_freq_time}s")
    print(f"Car Amp: {car_amp_start} to {car_amp_end} in {car_amp_time}s")
    return True

# Create triggers to update ramps when parameters change
param_trigger = Change(mod_freq_ramp_start + mod_freq_ramp_end + mod_freq_ramp_time + 
                       mod_amp_ramp_start + mod_amp_ramp_end + mod_amp_ramp_time + 
                       car_freq_ramp_start + car_freq_ramp_end + car_freq_ramp_time + 
                       car_amp_ramp_start + car_amp_ramp_end + car_amp_ramp_time).play()
param_updater = TrigFunc(param_trigger, update_ramps)

# === CALCULATE ACTUAL FM VALUES ===
# Modulator frequency calculation with ramp applied
# Scale the ramp effect for dramatically more noticeable modulations
modulator_base_freq = pitch * fm_ratio + mod_freq_offset
modulator_freq = modulator_base_freq + mod_freq_ramp * pitch  # Scale by pitch for proper octave shifts

# Calculate the peak frequency deviation with amplitude ramp applied
peak_deviation = pitch * fm_index * mod_index_env * mod_amp_ramp

# Create the actual modulator oscillator
modulator = Sine(freq=modulator_freq, mul=peak_deviation)

# === DIRECT FM - carrier frequency is affected by the modulator output plus carrier ramp ===
# Scale carrier ramp by pitch for proper octave shifts
carrier_freq = pitch + modulator + car_freq_ramp * pitch

# Create the carrier oscillator with the modulated frequency and amplitude ramp
carrier_amp_env = Adsr(attack=0.01, decay=0.1, sustain=0.8, release=0.5, dur=1, mul=.15)
carrier = Sine(freq=carrier_freq, mul=carrier_amp_env * velocity * (0.5 + aftertouch**2 * 2) * car_amp_ramp)

# === STEREO OUTPUT WITH CENTER PANNING ===
# Create a stereo panner set to center (0.5)
panner = Pan(carrier, outs=2, pan=0.5)

# === SCOPE VISUALIZATION ===
# Create scopes to visualize the signals
# 1. Modulator output (showing frequency modulation)
mod_scope = Scope(modulator, length=0.05, gain=1.0)

# 2. Final carrier output (showing the resulting waveform)
carrier_scope = Scope(carrier, length=0.05, gain=1.0)

# 3. Spectrum analyzer to show harmonic content
spectrum = Spectrum(panner, size=1024)

# === DEBUG MONITORING ===
# Monitor the modulator output and carrier frequency
def print_debug_values():
    base_pitch = pitch.get()
    mod_freq_val = modulator_freq.get()
    deviation_val = peak_deviation.get()
    car_freq_val = carrier_freq.get()
    
    print(f"Base pitch: {base_pitch:.1f} Hz")
    print(f"Modulator freq: {mod_freq_val:.1f} Hz (ratio: {fm_ratio.get():.2f})")
    print(f"Peak deviation: {deviation_val:.1f} Hz (index: {fm_index.get():.1f})")
    print(f"Carrier freq range: {base_pitch-deviation_val:.1f} to {base_pitch+deviation_val:.1f} Hz")
    print(f"Current carrier freq: {car_freq_val:.1f} Hz")
    
    # Monitor ramp values
    mod_freq_ramp_val = mod_freq_ramp.get()
    mod_amp_ramp_val = mod_amp_ramp.get()
    car_freq_ramp_val = car_freq_ramp.get()
    car_amp_ramp_val = car_amp_ramp.get()
    
    print(f"Mod Freq Ramp current: {mod_freq_ramp_val:.2f} * {base_pitch:.1f} = {mod_freq_ramp_val * base_pitch:.1f} Hz")
    print(f"Mod Amp Ramp current: {mod_amp_ramp_val:.2f}")
    print(f"Car Freq Ramp current: {car_freq_ramp_val:.2f} * {base_pitch:.1f} = {car_freq_ramp_val * base_pitch:.1f} Hz")
    print(f"Car Amp Ramp current: {car_amp_ramp_val:.2f}")
    print("-----------------------------")
    return True

# Create a trigger to print values when parameters change or periodically
debug_trigger = Metro(0.5).play()  # Print debug values every 0.5 seconds
debug_printer = TrigFunc(debug_trigger, print_debug_values)

# === GUI CONTROLS WITH IMPROVED RANGES ===
# Create slider controls for FM parameters
fm_ratio.ctrl(title="FM Ratio (modulator/carrier)")
fm_index.ctrl(title="FM Index (modulation depth)")
mod_freq_offset.ctrl(title="Modulator Frequency Offset (Hz)")

# LineSeq GUI controls for modulator with increased ranges
# For frequency ramps, use fractional values to indicate pitch shifting
# e.g., 1.0 = one octave up, -0.5 = perfect fifth down
mod_freq_ramp_start.ctrl(title="Mod Freq Ramp Start (ratio of pitch)")
mod_freq_ramp_end.ctrl(title="Mod Freq Ramp End (ratio of pitch)")
mod_freq_ramp_time.ctrl(title="Mod Freq Ramp Time (sec)")

# For amplitude ramps, allow values from 0 (silent) to 5 (loud)
mod_amp_ramp_start.ctrl(title="Mod Amp Ramp Start (0-5)")
mod_amp_ramp_end.ctrl(title="Mod Amp Ramp End (0-5)")
mod_amp_ramp_time.ctrl(title="Mod Amp Ramp Time (sec)")

# LineSeq GUI controls for carrier with increased ranges
car_freq_ramp_start.ctrl(title="Carrier Freq Ramp Start (ratio of pitch)")
car_freq_ramp_end.ctrl(title="Carrier Freq Ramp End (ratio of pitch)")
car_freq_ramp_time.ctrl(title="Carrier Freq Ramp Time (sec)")

car_amp_ramp_start.ctrl(title="Carrier Amp Ramp Start (0-5)")
car_amp_ramp_end.ctrl(title="Carrier Amp Ramp End (0-5)")
car_amp_ramp_time.ctrl(title="Carrier Amp Ramp Time (sec)")

# Envelope controls
mod_index_env.ctrl(title="Modulation Index Envelope")
carrier_amp_env.ctrl(title="Carrier Amplitude Envelope")

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

# Add manual volume control after limiting
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
            print("🛰", msg)
            if msg.type == 'note_on' and msg.velocity > 0:
                freq_val = 440.0 * (2 ** ((msg.note - 69) / 12))
                pitch.value = freq_val
                velocity.value = msg.velocity / 127
                carrier_amp_env.play()
                mod_index_env.play()
                
                # Force an update of the ramps with current values
                update_ramps()
                
                # Reset and play all ramps for each new note
                mod_freq_ramp.play()
                mod_amp_ramp.play()
                car_freq_ramp.play()
                car_amp_ramp.play()
                
                # Force a debug printout
                print_debug_values()
                current_note[0] = msg.note
            elif msg.type in ['note_off', 'note_on'] and msg.velocity == 0:
                if msg.note == current_note[0]:
                    carrier_amp_env.stop()
                    mod_index_env.stop()
                    # No need to stop ramps - they complete on their own
            elif msg.type == 'polytouch':
                if msg.note == current_note[0]:
                    aftertouch.value = msg.value / 127

# Run update_ramps once to initialize with starting values
update_ramps()

# Launch MIDI handler
Thread(target=midi_loop, daemon=True).start()

# GUI
s.gui(locals())
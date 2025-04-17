declare name "reliable_synth";
declare description "Ultra-reliable synthesizer with predictable sound";
declare version "1.0";

import("stdfaust.lib");

// Basic parameters - simplified for maximum reliability
freq = hslider("freq[osc:/freq]", 440, 20, 8000, 0.01);
gate = button("gate[osc:/gate]");
gain = hslider("gain[osc:/gain]", 0.8, 0, 1, 0.01);

// Simplified controls - only what's needed
wave_type = nentry("wave_type[osc:/wave_type]", 2, 0, 3, 1) : int;  // Default to sawtooth

// Just basic envelope (no filter to cause problems)
attack = hslider("attack[osc:/attack]", 0.01, 0.001, 2, 0.001);
release = hslider("release[osc:/release]", 0.3, 0.001, 2, 0.001);

// Individual simple waveforms
sine_wave = os.osc(freq);
triangle_wave = os.triangle(freq);
saw_wave = os.sawtooth(freq);
square_wave = os.square(freq);

// Simple selector with multiplication
oscillator = 
    (wave_type == 0) * sine_wave +
    (wave_type == 1) * triangle_wave +
    (wave_type == 2) * saw_wave +
    (wave_type == 3) * square_wave;

// Simple envelope
envelope = en.ar(attack, release, gate);

// Final output - no filter, just clean oscillator with envelope
process = oscillator * envelope * gain;
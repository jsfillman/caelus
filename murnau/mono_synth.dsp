declare name "mono_synth";
declare description "Monophonic synth optimized for rapid note transitions";
declare version "1.0";

import("stdfaust.lib");

// Basic parameters
freq = hslider("freq[osc:/freq]", 440, 20, 8000, 0.01);
gate = button("gate[osc:/gate]");
gain = hslider("gain[osc:/gain]", 1.0, 0, 1, 0.01);

// Waveform selector (0:sine, 1:triangle, 2:saw, 3:square)
wave_type = nentry("wave_type[osc:/wave_type]", 2, 0, 3, 1) : int;

// Generate all waveforms
sine_wave = os.osc(freq);
triangle_wave = os.triangle(freq);
saw_wave = os.sawtooth(freq);
square_wave = os.square(freq);

// Select waveform
oscillator = 
    (wave_type == 0) * sine_wave +
    (wave_type == 1) * triangle_wave +
    (wave_type == 2) * saw_wave +
    (wave_type == 3) * square_wave;

// Envelope optimized for rapid transitions
// - Very fast attack (1ms)
// - Moderate release for note tails (300ms)
env = en.ar(0.001, 0.3, gate);

// Final output
process = oscillator * env * gain;
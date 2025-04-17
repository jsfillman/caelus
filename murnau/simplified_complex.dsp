declare name "simplified_complex";
declare description "Simplified complex synth";
declare author "Claude";
declare version "1.0";

import("stdfaust.lib");

// Basic control parameters
freq = hslider("freq[osc:/freq]", 440, 20, 8000, 0.01);
gate = button("gate[osc:/gate]");
gain = hslider("gain[osc:/gain]", 0.5, 0, 1, 0.01);

// Oscillator section
wave_type = nentry("wave_type[osc:/wave_type]", 0, 0, 3, 1) : int; // 0:sine, 1:tri, 2:saw, 3:square

// Simple envelope
attack = hslider("attack[osc:/attack]", 0.01, 0.001, 2, 0.001);
release = hslider("release[osc:/release]", 0.1, 0.001, 2, 0.001);

// Filter controls
cutoff = hslider("cutoff[osc:/cutoff]", 2000, 20, 20000, 0.1);
resonance = hslider("resonance[osc:/resonance]", 0.5, 0, 0.95, 0.01);

// Individual oscillators
sine_osc = os.osc(freq);
triangle_osc = os.triangle(freq);
sawtooth_osc = os.sawtooth(freq);
square_osc = os.square(freq);

// Waveform selection 
osc_output = 
    (wave_type == 0) * sine_osc +
    (wave_type == 1) * triangle_osc +
    (wave_type == 2) * sawtooth_osc +
    (wave_type == 3) * square_osc;

// Apply filter
filtered = fi.resonlp(cutoff, resonance, osc_output);

// Apply envelope
envelope = en.ar(attack, release, gate);

// Final output
process = filtered * envelope * gain;
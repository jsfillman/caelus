declare name "medium_synth";
declare description "Medium complexity synth with OSC control";
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

// Individual oscillators
sine_osc = os.osc(freq);
triangle_osc = os.triangle(freq);
sawtooth_osc = os.sawtooth(freq);
square_osc = os.square(freq);

// Waveform selection using if-else construction
osc_output = 
    (wave_type == 0) * sine_osc +
    (wave_type == 1) * triangle_osc +
    (wave_type == 2) * sawtooth_osc +
    (wave_type == 3) * square_osc;

// Apply envelope
envelope = en.ar(attack, release, gate);

// Final output
process = osc_output * envelope * gain;
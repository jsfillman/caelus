declare name "multi_synth";
declare description "Multi-waveform synth with filter";
declare version "1.0";

import("stdfaust.lib");

// Basic parameters
freq = hslider("freq[osc:/freq]", 440, 20, 8000, 0.01);
gate = button("gate[osc:/gate]");
gain = hslider("gain[osc:/gain]", 0.8, 0, 1, 0.01);  // Higher default gain

// Waveform selection (0:sine, 1:triangle, 2:saw, 3:square)
wave_type = nentry("wave_type[osc:/wave_type]", 2, 0, 3, 1);  // Default to sawtooth (more audible)

// Filter parameters
filter_on = checkbox("filter_on[osc:/filter_on]") : int;  // Explicit cast to int
cutoff = hslider("cutoff[osc:/cutoff]", 8000, 20, 12000, 1);  // Higher default cutoff
resonance = hslider("resonance[osc:/resonance]", 0.3, 0, 0.95, 0.01);  // Lower default resonance

// Envelope parameters
attack = hslider("attack[osc:/attack]", 0.01, 0.001, 4, 0.001);  // Fast attack
release = hslider("release[osc:/release]", 0.5, 0.001, 5, 0.001);  // Longer release

// Generate each waveform
sine_wave = os.osc(freq);
triangle_wave = os.triangle(freq);
saw_wave = os.sawtooth(freq);
square_wave = os.square(freq);

// Select waveform based on control
oscillator = 
    (wave_type == 0) * sine_wave +
    (wave_type == 1) * triangle_wave +
    (wave_type == 2) * saw_wave +
    (wave_type == 3) * square_wave;

// Filter the signal conditionally
filtered = filter_on * fi.resonlp(cutoff, resonance, oscillator) + (1 - filter_on) * oscillator;

// Apply envelope
envelope = en.ar(attack, release, gate);

// Final output
process = filtered * envelope * gain;
declare name "legato_synth";
declare description "Monophonic synth with legato capability";
declare version "1.0";

import("stdfaust.lib");

// Basic parameters
freq = hslider("freq[osc:/freq]", 440, 20, 8000, 0.01);
gate = button("gate[osc:/gate]");
gain = hslider("gain[osc:/gain]", 1.0, 0, 1, 0.01);

// Waveform selector (0:sine, 1:triangle, 2:saw, 3:square)
wave_type = nentry("wave_type[osc:/wave_type]", 2, 0, 3, 1) : int;

// ADSR envelope with longer sustain and release
attack = hslider("attack[osc:/attack]", 0.005, 0.001, 1, 0.001);
decay = hslider("decay[osc:/decay]", 0.1, 0.001, 1, 0.001);
sustain = hslider("sustain[osc:/sustain]", 0.9, 0, 1, 0.01);
release = hslider("release[osc:/release]", 0.5, 0.1, 2, 0.01);

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

// Full ADSR envelope for better control
env = en.adsr(attack, decay, sustain, release, gate);

// Final output
process = oscillator * env * gain;
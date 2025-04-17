declare name "step3_waveforms";
declare description "Synth with waveform selection";
declare version "1.0";

import("stdfaust.lib");

// Basic parameters
freq = hslider("freq[osc:/freq]", 440, 20, 2000, 0.1);
gain = hslider("gain[osc:/gain]", 0.5, 0, 1, 0.01);
gate = button("gate[osc:/gate]");

// Waveform selection
wave_type = nentry("wave_type[osc:/wave_type]", 0, 0, 3, 1);

// Filter parameters
cutoff = hslider("cutoff[osc:/cutoff]", 2000, 20, 10000, 0.1);
resonance = hslider("resonance[osc:/resonance]", 0.5, 0, 0.95, 0.01);

// Envelope parameters
attack = hslider("attack[osc:/attack]", 0.01, 0.001, 2, 0.001);
decay = hslider("decay[osc:/decay]", 0.05, 0.001, 2, 0.001);
sustain = hslider("sustain[osc:/sustain]", 0.8, 0, 1, 0.01);
release = hslider("release[osc:/release]", 0.1, 0.001, 5, 0.001);

// Individual oscillator waves
sine = os.osc(freq);
triangle = os.triangle(freq);
sawtooth = os.sawtooth(freq);
square = os.square(freq);

// Waveform selection (using multiplication for mux)
oscillator = 
    (wave_type == 0) * sine +
    (wave_type == 1) * triangle +
    (wave_type == 2) * sawtooth +
    (wave_type == 3) * square;

// Filter
filtered = fi.resonlp(cutoff, resonance, oscillator);

// Envelope
envelope = en.adsr(attack, decay, sustain, release, gate);

// Final output
process = filtered * envelope * gain;
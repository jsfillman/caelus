declare name "simple";
declare description "Simple polyphonic synth with 4-pole LPF";
declare version "1.0";
// declare options "[nvoices:8][osc:on]";  // Disabled polyphony for simpler OSC addressing

import("stdfaust.lib");

// === Gate ===
gate = button("gate[osc:/gate]");

// === Frequency ===
freq = hslider("freq[osc:/freq]", 440, 20, 8000, 0.01);

// === Amplitude ===
gain = hslider("gain[osc:/gain]", 0.8, 0, 1, 0.01);

// === Filter Controls ===
cutoff = hslider("cutoff[osc:/cutoff]", 1000, 20, 20000, 1);
resonance = hslider("resonance[osc:/resonance]", 0.5, 0.1, 4, 0.01);

// === Signal Path ===
env = gate : si.smooth(0.01);
osc = os.sawtooth(freq);
signal = osc * env * gain;

// === Filter ===
// Double resonlp for 4-pole (24dB/octave) lowpass 
filtered = signal : fi.resonlp(cutoff, resonance, 1.0) : fi.resonlp(cutoff, resonance, 1.0);

// === Output ===
process = filtered <: _, _;

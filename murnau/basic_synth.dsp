declare name "basic_synth";
declare description "Absolute minimum synth - just a sawtooth oscillator";
declare version "1.0";

import("stdfaust.lib");

// Only the absolutely necessary parameters
freq = hslider("freq[osc:/freq]", 440, 20, 8000, 0.01);
gate = button("gate[osc:/gate]");
gain = hslider("gain[osc:/gain]", 1.0, 0, 1, 0.01); // Default to maximum gain

// No waveform selection - just use sawtooth (most audible)
// No filter - just pure oscillator
// No complex envelope - instant attack, medium release

// Simple envelope with instant attack
env = en.ar(0.001, 0.5, gate);

// Final output - just sawtooth with envelope
process = os.sawtooth(freq) * env * gain;
declare name "step1_filter";
declare description "Simple synth with filter added";
declare version "1.0";

import("stdfaust.lib");

// Basic parameters
freq = hslider("freq[osc:/freq]", 440, 20, 2000, 0.1);
gain = hslider("gain[osc:/gain]", 0.5, 0, 1, 0.01);
gate = button("gate[osc:/gate]");

// Add filter parameters
cutoff = hslider("cutoff[osc:/cutoff]", 2000, 20, 10000, 0.1);
resonance = hslider("resonance[osc:/resonance]", 0.5, 0, 0.95, 0.01);

// Simple oscillator with filter
oscillator = os.osc(freq); // Sine wave
filtered = fi.resonlp(cutoff, resonance, oscillator);

// Final output
process = filtered * gate * gain;
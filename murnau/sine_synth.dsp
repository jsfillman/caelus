declare name "sine_synth";
declare description "Super-simple sine wave synth with OSC";
declare version "1.0";

import("stdfaust.lib");

// Super minimal - just frequency, gate and gain
freq = hslider("freq[osc:/freq]", 440, 20, 8000, 0.01);
gate = button("gate[osc:/gate]");
gain = hslider("gain[osc:/gain]", 0.5, 0, 1, 0.01);

// Just a sine oscillator with gate and gain
process = os.osc(freq) * gate * gain;
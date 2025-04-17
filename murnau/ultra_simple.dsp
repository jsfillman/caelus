declare name "ultra_simple";
declare description "Ultra simple test synth";
declare version "1.0";

import("stdfaust.lib");

// Simplest possible synth with OSC control and one oscillator
freq = hslider("freq[osc:/freq]", 440, 20, 2000, 0.1);
gain = hslider("gain[osc:/gain]", 0.5, 0, 1, 0.01);
gate = button("gate[osc:/gate]");

// Just a sine wave oscillator with gain and gate
process = os.osc(freq) * gate * gain;
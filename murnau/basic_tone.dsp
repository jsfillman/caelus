declare name "basic_tone";
declare description "Simple tone generator with no OSC controls";
declare author "Claude";
declare version "1.0";

import("stdfaust.lib");

// Simple fixed parameters - no OSC
freq = 440;  // Fixed A4 note
gain = 0.5;  // Fixed moderate volume

// Simple sine wave oscillator
process = os.osc(freq) * gain;
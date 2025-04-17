declare name "simple_osc";
declare description "Minimal OSC-controlled tone generator";
declare author "Claude";
declare version "1.0";

import("stdfaust.lib");

// Just two simple OSC parameters
freq = hslider("freq[osc:/freq]", 440, 20, 8000, 0.01);
gate = button("gate[osc:/gate]");

// Simple sine oscillator with on/off control
process = os.osc(freq) * gate * 0.5;
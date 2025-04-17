declare name "simple_saw";
declare description "Simple OSC-controlled sawtooth";
declare version "1.0";

import("stdfaust.lib");

// Explicitly define full OSC path
freq = nentry("freq[osc:/freq]", 440, 20, 2000, 0.1);
gate = button("gate[osc:/gate]");

// Simple sawtooth wave with gate
process = os.sawtooth(freq) * gate * 0.25;
declare name "saw_synth";
declare description "Simple sawtooth synth with OSC control";
declare author "Claude";
declare version "1.0";

import("stdfaust.lib");

// OSC parameters
freq = nentry("freq[osc:/freq]", 440, 20, 20000, 0.01);
gate = button("gate[osc:/gate]");

// Sawtooth oscillator with envelope
process = os.sawtooth(freq) * gate * 0.5; 
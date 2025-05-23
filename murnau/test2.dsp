import("stdfaust.lib");

result = ba.sAndH(gate, no.noise);  // 👈 using gate before it's defined
gate = button("gate");

process = result <: _, _;


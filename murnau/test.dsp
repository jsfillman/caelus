import("stdfaust.lib");
gate = button("gate");
stability = hslider("stability", 10, 0, 100, 1);
noise = no.noise * 2 - 1;
sampled = ba.sAndH(gate, noise);
rand_stab = sampled * stability;
process = rand_stab <: _, _;


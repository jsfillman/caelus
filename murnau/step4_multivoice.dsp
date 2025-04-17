declare name "step4_multivoice";
declare description "Multi-voice synth";
declare version "1.0";

import("stdfaust.lib");

// Basic parameters
freq = hslider("freq[osc:/freq]", 440, 20, 2000, 0.1);
gain = hslider("gain[osc:/gain]", 0.5, 0, 1, 0.01);
gate = button("gate[osc:/gate]");

// Waveform selection
wave_type = nentry("wave_type[osc:/wave_type]", 0, 0, 3, 1);

// Filter parameters
cutoff = hslider("cutoff[osc:/cutoff]", 2000, 20, 10000, 0.1);
resonance = hslider("resonance[osc:/resonance]", 0.5, 0, 0.95, 0.01);

// Envelope parameters
attack = hslider("attack[osc:/attack]", 0.01, 0.001, 2, 0.001);
decay = hslider("decay[osc:/decay]", 0.05, 0.001, 2, 0.001);
sustain = hslider("sustain[osc:/sustain]", 0.8, 0, 1, 0.01);
release = hslider("release[osc:/release]", 0.1, 0.001, 5, 0.001);

// Voice parameters
voice1_level = hslider("voice1/level[osc:/voice1/level]", 0.8, 0, 1, 0.01);
voice1_detune = hslider("voice1/detune[osc:/voice1/detune]", 0, -50, 50, 0.1);

voice2_level = hslider("voice2/level[osc:/voice2/level]", 0.6, 0, 1, 0.01);
voice2_detune = hslider("voice2/detune[osc:/voice2/detune]", 7, -50, 50, 0.1);

// Calculate actual frequencies for each voice with detune
freq1 = freq * (2 ^ (voice1_detune/1200));
freq2 = freq * (2 ^ (voice2_detune/1200));

// Individual oscillator waves for voice 1
sine1 = os.osc(freq1);
triangle1 = os.triangle(freq1);
sawtooth1 = os.sawtooth(freq1);
square1 = os.square(freq1);

// Voice 1 waveform selection
voice1 = 
    (wave_type == 0) * sine1 +
    (wave_type == 1) * triangle1 +
    (wave_type == 2) * sawtooth1 +
    (wave_type == 3) * square1;

// Individual oscillator waves for voice 2
sine2 = os.osc(freq2);
triangle2 = os.triangle(freq2);
sawtooth2 = os.sawtooth(freq2);
square2 = os.square(freq2);

// Voice 2 waveform selection
voice2 = 
    (wave_type == 0) * sine2 +
    (wave_type == 1) * triangle2 +
    (wave_type == 2) * sawtooth2 +
    (wave_type == 3) * square2;

// Mix voices with their levels
oscillator_mix = voice1 * voice1_level + voice2 * voice2_level;

// Filter
filtered = fi.resonlp(cutoff, resonance, oscillator_mix);

// Envelope
envelope = en.adsr(attack, decay, sustain, release, gate);

// Final output
process = filtered * envelope * gain;
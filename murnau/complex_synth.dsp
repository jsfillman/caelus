declare name "complex_synth";
declare description "Complex synthesizer with OSC control";
declare author "Claude";
declare version "1.0";

import("stdfaust.lib");

// Main control parameters
freq = hslider("freq[osc:/freq]", 440, 20, 8000, 0.01);
gate = button("gate[osc:/gate]");
gain = hslider("gain[osc:/gain]", 0.5, 0, 1, 0.01);

// Oscillator 1 controls
osc1_waveform = nentry("osc1/waveform[osc:/osc1/waveform]", 0, 0, 3, 1) : int; // 0:sine, 1:tri, 2:saw, 3:square
osc1_level = hslider("osc1/level[osc:/osc1/level]", 0.7, 0, 1, 0.01);
osc1_octave = nentry("osc1/octave[osc:/osc1/octave]", 0, -2, 2, 1) : int;

// Oscillator 2 controls
osc2_waveform = nentry("osc2/waveform[osc:/osc2/waveform]", 2, 0, 3, 1) : int; 
osc2_level = hslider("osc2/level[osc:/osc2/level]", 0.5, 0, 1, 0.01);
osc2_octave = nentry("osc2/octave[osc:/osc2/octave]", 0, -2, 2, 1) : int;
osc2_detune = hslider("osc2/detune[osc:/osc2/detune]", 7, -50, 50, 0.1);

// Oscillator 3 controls
osc3_waveform = nentry("osc3/waveform[osc:/osc3/waveform]", 3, 0, 3, 1) : int;
osc3_level = hslider("osc3/level[osc:/osc3/level]", 0.3, 0, 1, 0.01);
osc3_octave = nentry("osc3/octave[osc:/osc3/octave]", -1, -2, 2, 1) : int;
osc3_detune = hslider("osc3/detune[osc:/osc3/detune]", -5, -50, 50, 0.1);

// Filter controls
cutoff = hslider("filter/cutoff[osc:/filter/cutoff]", 2000, 20, 20000, 0.1);
resonance = hslider("filter/resonance[osc:/filter/resonance]", 0.5, 0, 0.95, 0.01);

// Amplitude envelope
attack = hslider("env/attack[osc:/env/attack]", 0.01, 0.001, 2, 0.001);
decay = hslider("env/decay[osc:/env/decay]", 0.3, 0.001, 2, 0.001);
sustain = hslider("env/sustain[osc:/env/sustain]", 0.7, 0, 1, 0.01);
release = hslider("env/release[osc:/env/release]", 0.2, 0.001, 5, 0.001);

// Calculate frequencies for each oscillator with octave and detune
freq1 = freq * (2 ^ osc1_octave);
freq2 = freq * (2 ^ osc2_octave) * (2 ^ (osc2_detune/1200));
freq3 = freq * (2 ^ osc3_octave) * (2 ^ (osc3_detune/1200));

// Function to create oscillator with selectable waveform
oscillator(wf, f) = 
    (wf == 0) * os.osc(f) +
    (wf == 1) * os.triangle(f) +
    (wf == 2) * os.sawtooth(f) +
    (wf == 3) * os.square(f);

// Oscillator outputs
osc1_out = oscillator(osc1_waveform, freq1) * osc1_level;
osc2_out = oscillator(osc2_waveform, freq2) * osc2_level;
osc3_out = oscillator(osc3_waveform, freq3) * osc3_level;

// Mix all oscillators
osc_mix = osc1_out + osc2_out + osc3_out;

// Apply filter
filtered = fi.resonlp(cutoff, resonance, osc_mix);

// Apply envelope
envelope = en.adsr(attack, decay, sustain, release, gate);

// Final output
process = filtered * envelope * gain;
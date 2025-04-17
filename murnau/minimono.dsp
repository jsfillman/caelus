declare name "minimono";
declare description "Classic monophonic synthesizer with OSC control";
declare author "Claude";
declare version "1.0";

import("stdfaust.lib");

// OSC Control Parameters - Main
freq = hslider("freq[osc:/freq]", 440, 20, 8000, 0.01);
gate = button("gate[osc:/gate]");
gain = hslider("gain[osc:/gain]", 0.5, 0, 1, 0.01);

// Oscillators
osc1_waveform = hslider("osc1/waveform[osc:/osc1/waveform]", 0, 0, 3, 1) : int; // 0:sine, 1:tri, 2:saw, 3:square
osc1_oct = hslider("osc1/octave[osc:/osc1/octave]", 0, -2, 2, 1) : int;
osc1_level = hslider("osc1/level[osc:/osc1/level]", 0.7, 0, 1, 0.01);

osc2_waveform = hslider("osc2/waveform[osc:/osc2/waveform]", 2, 0, 3, 1) : int; // 0:sine, 1:tri, 2:saw, 3:square
osc2_oct = hslider("osc2/octave[osc:/osc2/octave]", 0, -2, 2, 1) : int;
osc2_detune = hslider("osc2/detune[osc:/osc2/detune]", 0, -50, 50, 0.1);
osc2_level = hslider("osc2/level[osc:/osc2/level]", 0.7, 0, 1, 0.01);

osc3_waveform = hslider("osc3/waveform[osc:/osc3/waveform]", 3, 0, 3, 1) : int; // 0:sine, 1:tri, 2:saw, 3:square
osc3_oct = hslider("osc3/octave[osc:/osc3/octave]", -1, -2, 2, 1) : int;
osc3_detune = hslider("osc3/detune[osc:/osc3/detune]", -7, -50, 50, 0.1);
osc3_level = hslider("osc3/level[osc:/osc3/level]", 0.5, 0, 1, 0.01);

// Filter
cutoff = hslider("filter/cutoff[osc:/filter/cutoff]", 2000, 20, 20000, 0.1);
resonance = hslider("filter/resonance[osc:/filter/resonance]", 0.5, 0, 0.99, 0.01);
env_amt = hslider("filter/env_amt[osc:/filter/env_amt]", 0.5, 0, 1, 0.01);

// Envelopes
// Filter envelope
f_attack = hslider("filter/env/attack[osc:/filter/env/attack]", 0.01, 0.001, 4, 0.001);
f_decay = hslider("filter/env/decay[osc:/filter/env/decay]", 0.3, 0.001, 4, 0.001);
f_sustain = hslider("filter/env/sustain[osc:/filter/env/sustain]", 0.5, 0, 1, 0.01);
f_release = hslider("filter/env/release[osc:/filter/env/release]", 0.5, 0.001, 8, 0.001);

// Amplitude envelope
a_attack = hslider("amp/env/attack[osc:/amp/env/attack]", 0.01, 0.001, 4, 0.001);
a_decay = hslider("amp/env/decay[osc:/amp/env/decay]", 0.05, 0.001, 4, 0.001);
a_sustain = hslider("amp/env/sustain[osc:/amp/env/sustain]", 0.8, 0, 1, 0.01);
a_release = hslider("amp/env/release[osc:/amp/env/release]", 0.5, 0.001, 8, 0.001);

// Generate waveforms
sine(f) = os.osc(f);
triangle(f) = os.triangle(f);
sawtooth(f) = os.sawtooth(f);
square(f) = os.square(f);

// Select waveform based on parameter
select_waveform(wf, f) = 
    (wf == 0) * sine(f) +
    (wf == 1) * triangle(f) +
    (wf == 2) * sawtooth(f) + 
    (wf == 3) * square(f);

// Oscillator frequencies with octave and detune
freq1 = freq * (2 ^ osc1_oct);
freq2 = freq * (2 ^ osc2_oct) * (2 ^ (osc2_detune/1200));
freq3 = freq * (2 ^ osc3_oct) * (2 ^ (osc3_detune/1200));

// Envelopes
filterEnv = en.adsr(f_attack, f_decay, f_sustain, f_release, gate);
ampEnv = en.adsr(a_attack, a_decay, a_sustain, a_release, gate);

// Oscillator mix
oscMix = 
    select_waveform(osc1_waveform, freq1) * osc1_level +
    select_waveform(osc2_waveform, freq2) * osc2_level +
    select_waveform(osc3_waveform, freq3) * osc3_level;

// Dynamic filter cutoff controlled by envelope
filteredOsc = fi.resonlp(
    cutoff + (filterEnv * env_amt * 10000), 
    resonance, 
    oscMix
);

// Final output with amp envelope
process = filteredOsc * ampEnv * gain;
// Caelux Mini - Initial Faust DSP Core
// This is a prototype of one oscillator unit (with envelope, filter, feedback, and delay)

import("stdfaust.lib");

//----------------------------------------------
// Basic parameters (to be replaced with UI controls)
//----------------------------------------------
freq = hslider("freq[unit:Hz]", 440, 20, 20000, 1);
gate = button("gate");
waveType = hslider("waveType[switch:sine:tri:saw:square]", 0, 0, 3, 1);
feedbackAmt = hslider("feedback[unit:%]", 0.2, 0, 1, 0.01);

//----------------------------------------------
// ADSR Envelope
//----------------------------------------------
attack = hslider("amp_env/attack", 0.01, 0, 5, 0.01);
decay = hslider("amp_env/decay", 0.2, 0, 5, 0.01);
sustain = hslider("amp_env/sustain", 0.8, 0, 1, 0.01);
release = hslider("amp_env/release", 0.5, 0, 5, 0.01);
ampEnv = en.adsr(attack, decay, sustain, release, gate);

//----------------------------------------------
// Waveform Selection (Fully Compatible)
//----------------------------------------------
oscBank(f) = select2(waveType < 2,
  select2(waveType == 0, os.osc(f), os.triangle(f)),
  select2(waveType == 2, os.sawtooth(f), os.square(f))
);

//----------------------------------------------
// Filter (lowpass with resonance) — mono version
//----------------------------------------------
cutoff = hslider("filter/cutoff", 5000, 20, 20000, 1);
resonance = hslider("filter/res", 0.1, 0, 1, 0.01);
filtered = fi.lowpass(1, cutoff) : *(1 - resonance);

//----------------------------------------------
// Stereo Delay with feedback
//----------------------------------------------
del1 = hslider("delay/left_time", 0.1, 0, 2, 0.01);
del2 = hslider("delay/right_time", 0.2, 0, 2, 0.01);
delFB = hslider("delay/feedback", 0.3, 0, 1, 0.01);
feedbackDelay(x, time, fb) = (x + fb) : de.delay(time) ~ _;

//----------------------------------------------
// Signal Chain (no oscillator feedback yet)
//----------------------------------------------
signal = oscBank(freq) * ampEnv : filtered;
delayL = feedbackDelay(signal, del1, delFB);
delayR = feedbackDelay(signal, del2, delFB);
process = delayL, delayR;


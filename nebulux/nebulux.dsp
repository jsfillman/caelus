// Nebulux.dsp - Swarming Morphing Oscillator Bank (Phase 1)
import("stdfaust.lib");

// === User Controls ===
numOscs      = int(hslider("/Nebulux/numOscs", 8, 1, 20, 1));
waveScan     = hslider("/Nebulux/waveScan", 0.0, 0.0, 1.0, 0.01);
spread       = hslider("/Nebulux/spread", 5.0, 0.0, 100.0, 0.1);
spreadMode   = checkbox("/Nebulux/spreadModeHz") : int; // 0 = cents, 1 = Hz
phaseSpread  = hslider("/Nebulux/phaseSpread", 6.28, 0.0, 6.28, 0.01);
stereoSpread = hslider("/Nebulux/stereoSpread", 1.0, 0.0, 1.0, 0.01);
gain         = hslider("/Nebulux/gain", 0.2, 0.0, 1.0, 0.01);

// === Wavetables (basic morph scan) ===
t1(freq) = os.osc(freq);                    // sine
t2(freq) = os.square(freq);
t3(freq) = os.triangle(freq);
t4(freq) = os.saw(freq);

interp(freq, scan) = (
  select2(t1(freq), t2(freq), scan * 3.0) * (scan < 0.33) +
  select2(t2(freq), t3(freq), (scan - 0.33) * 3.0) * (scan >= 0.33 && scan < 0.66) +
  select2(t3(freq), t4(freq), (scan - 0.66) * 3.0) * (scan >= 0.66)
);

// === Detune spread in Hz or cents ===
spreadFn(baseFreq, i, n) =
  baseFreq * (spreadMode == 0 ? pow(2, ((i - n/2.0) * spread) / 1200.0) :
                                  (1 + ((i - n/2.0) * spread / baseFreq)));

// === Phase and Stereo Pan Spread ===
phaseFn(i, n) = (i * phaseSpread / n);
panFn(i, n) = ((i - (n/2.0)) / (n/2.0)) * stereoSpread;

oscillator(i, baseFreq, amp, n) =
  osc = interp(spreadFn(baseFreq, i, n), waveScan) * amp : si.smoo;
  pan = panFn(i, n);
  (osc * (1 - pan), osc * (1 + pan));

voice(freq, amp) =
  oscs = par(i, numOscs, oscillator(i, freq, amp/numOscs, numOscs));
  mixL = par(i, numOscs, oscs[i*2]);
  mixR = par(i, numOscs, oscs[i*2+1]);
  (sum(mixL), sum(mixR)) * gain;

process = pm.voice(voice);

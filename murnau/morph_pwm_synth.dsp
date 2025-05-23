//=====================================================
//  morph_pwm_synth_mono.dsp
//  Mono morphable oscillator with PWM and single filter
//=====================================================

import("stdfaust.lib");

// Main process
process = synth <: _,_;

// Simple mono synth
synth = oscillator : filter : amp_envelope
with {
    // Basic controls
    gate = button("gate[osc:/gate]");
    gain = hslider("gain[osc:/gain]", 0.3, 0, 1, 0.01);
    
    // Base frequency
    freq = hslider("freq[osc:/freq]", 440, 20, 8000, 0.01);
    
    // Single envelope
    attack = hslider("attack[osc:/attack]", 0.01, 0.001, 5, 0.001);
    decay = hslider("decay[osc:/decay]", 0.1, 0.001, 3, 0.001);
    sustain = hslider("sustain[osc:/sustain]", 0.9, 0, 1, 0.01);
    release = hslider("release[osc:/release]", 0.5, 0.1, 5, 0.01);
    env = en.adsr(attack, decay, sustain, release, gate);
    
    // Morphing and PWM
    morph = hslider("morph[osc:/morph]", 0, 0, 2, 0.01);
    pwm_rate = hslider("pwm_rate[osc:/pwm_rate]", 1.0, 0.01, 20, 0.01);
    pwm_depth = hslider("pwm_depth[osc:/pwm_depth]", 0.5, 0, 1, 0.01);
    
    // Generate phase with PWM
    phase = os.phasor(freq);
    pwm_mod = os.osc(pwm_rate) * pwm_depth * 0.5;
    mod_phase = phase + pwm_mod;
    
    // Generate basic waveforms
    tri = os.triangle(phase * 2 * ma.PI);
    saw = os.sawtooth(phase * 2 * ma.PI);
    sqr = os.square(mod_phase * 2 * ma.PI);
    
    // Morphing between waveforms
    tri_saw = (1-morph)*tri + morph*saw;
    saw_sqr = (2-morph)*saw + (morph-1)*sqr;
    
    // Oscillator output based on morph position
    oscillator = select2(morph>1, tri_saw, saw_sqr);
    
    // Single filter
    cutoff = hslider("cutoff[osc:/cutoff]", 2000, 20, 20000, 1);
    resonance = hslider("resonance[osc:/resonance]", 0.5, 0.1, 4, 0.01);
    filter = fi.resonlp(cutoff, resonance, 1.0);
    
    // Apply envelope and gain
    amp_envelope = *(env) : *(gain);
};
// caelux_osc.dsp - Basic MIDI-controlled oscillator
import("stdfaust.lib");

// MIDI handling
freq = nentry("freq[midi:pitchwheel]", 440, 20, 20000, 1);
gain = nentry("gain[midi:ctrl 7]", 0.5, 0, 1, 0.01);
gate = button("gate[midi:key]");

// Envelope
envelope = en.adsr(0.01, 0.1, 0.8, 0.5, gate);

// Oscillator with selectable waveform
wave_type = hslider("wave_type[style:menu{'sine':0;'saw':1;'square':2;'triangle':3}]", 0, 0, 3, 1);
oscillator = ba.selectn(4, wave_type, 
                        os.osc(freq), 
                        os.sawtooth(freq), 
                        os.square(freq), 
                        os.triangle(freq));

// Process
process = oscillator * envelope * gain <: _,_;

import("stdfaust.lib");

gate = button("gate");
base_freq = hslider("freq", 440, 20, 2000, 1);
ramp_time = hslider("ramp_time", 1, 0, 10, 0.1);
start_offset = hslider("start_freq", 0, -500, 500, 1);
end_offset = hslider("end_freq", 0, -500, 500, 1);

ramp = en.ar(gate, ramp_time);
freq_offset = start_offset + (end_offset - start_offset) * ramp;
freq = base_freq + freq_offset;

process = os.osc(freq) <: _, _;


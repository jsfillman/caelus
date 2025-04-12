import pyo

class Oscillator:
    def __init__(self, base_freq_sig, amp_sig, vol_sig, out_chnl, waveform_bank, table_name):
        self.waveform_bank = waveform_bank 
        self.table_name = table_name 
        self.table = waveform_bank.get_table(table_name)
        self.semi = pyo.Sig(0)
        self.cents = pyo.Sig(0)

        # === ADSR envelope ===
        self.attack_val = 0.01
        self.decay_val = 0.1
        self.sustain_val = 0.5
        self.release_val = 0.1
        self.env = pyo.Adsr(
            attack=self.attack_val,
            decay=self.decay_val,
            sustain=self.sustain_val,
            release=self.release_val,
            dur=0,
            mul=amp_sig * vol_sig
        )

        # === Detuning ===
        self.detune = 2 ** ((self.semi / 12.0) + (self.cents / 1200.0))

        # === Oscillator (not yet routed to output)
        self.osc = pyo.Osc(
            table=self.table,
            freq=base_freq_sig * self.detune,
            mul=self.env
        )

        # === Filter LFO Modulation ===
        self.cutoff = pyo.Sig(1000)           # base cutoff in Hz
        self.lfo_rate = pyo.Sig(0.2)          # LFO speed in Hz
        self.lfo_depth = pyo.Sig(800)         # LFO modulation depth in Hz
        self.resonance = pyo.Sig(0.7)         # resonance (0–1)

        self.lfo = pyo.Sine(freq=self.lfo_rate, mul=self.lfo_depth)
        self.modulated_cutoff = self.cutoff + self.lfo

        # === Moog low-pass filter with modulated cutoff
        self.filtered = pyo.MoogLP(
            input=self.osc,
            freq=self.modulated_cutoff,
            res=self.resonance
        ).out(chnl=out_chnl)

    def get_ui_controls(self):
        return (
            self.semi, self.cents, self,
            self.cutoff, self.lfo_rate, self.lfo_depth, self.resonance
        )


    def set_waveform(self, table_name):
        self.table_name = table_name
        new_table = self.waveform_bank.get_table(table_name)
        self.osc.setTable(new_table)

    # === ADSR controls
    def set_attack(self, val): self.attack_val = val; self.env.setAttack(val)
    def set_decay(self, val): self.decay_val = val; self.env.setDecay(val)
    def set_sustain(self, val): self.sustain_val = val; self.env.setSustain(val)
    def set_release(self, val): self.release_val = val; self.env.setRelease(val)

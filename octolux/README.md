# Octolux

![Octolux Logo](Octolux.png)

**Octolux** is a modular 8-oscillator wavetable synthesizer built with Python and [pyo](http://ajaxsoundstudio.com/software/pyo/).  
Designed for immersive sound design and real-time control, it features per-oscillator detuning, envelope shaping, and filter modulation — all routed independently for surround/spatial mixing in Dolby Atmos or multi-channel environments.

---

## 🎛 Features

- **8 fully independent oscillators**
  - Selectable wavetables per oscillator
  - Semitone and cents detuning
  - ADSR envelopes with real-time GUI control
  - Moog-style low-pass filter with resonance
  - LFO-modulated filter cutoff (rate + depth)
- **Per-oscillator audio routing** to discrete output channels
- **PyQt6 GUI** with waveform selector and grouped control layout
- Compatible with **Blackhole** or other virtual audio interfaces for DAW routing
- Designed for **Logic Pro Atmos mixing**, but works in stereo too

---

## 🔧 Requirements

- Python 3.10+
- `pyo`
- `PyQt6`
- [Blackhole](https://existential.audio/blackhole/) (for multi-channel routing)

Install dependencies:

```bash
pip install pyo PyQt6


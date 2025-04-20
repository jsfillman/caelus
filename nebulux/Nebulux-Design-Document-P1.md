# Nebulux: Design Document (Phase 1)

## Overview
Nebulux is a high-performance, polyphonic, morphing wavetable oscillator bank implemented in Faust. It is controlled via OSC, with optional MIDI support routed from a PyQt6 GUI controller.

This document outlines the design for Phase 1: a single oscillator bank with rich detuning, stereo spread, wave morphing, and OSC-based control.

---

## Goals (Phase 1)
- Build a single oscillator bank in Faust
- Support polyphonic note-on/off via OSC
- Add configurable wavetable morphing, detune spread, stereo and phase spread
- Create a test Python script to send OSC note events

---

## Features

### Oscillator Bank (Faust DSP)
- **Wavetable Morphing**: Morph between 2–4 waveforms (sine, saw, square, triangle)
- **Waveform Selection**: Enum-based table index control
- **Num Oscillators**: 1–20 oscillators per note
- **Detune Spread**: Toggle between Hz and Cents
- **Phase Spread**: Evenly distribute or randomize phase across oscillators
- **Stereo Spread**: Spread oscillators across stereo field
- **Master Gain**: Global volume control
- **OSC Control Paths**: Expose all parameters and note events
- **Polyphony**: Handled via `faust2poly` with voice count defined at compile time

### OSC Note Input (Phase 1 test script)
- Python script using `python-osc`
- Sends:
  - `/Nebulux/noteon` [note, velocity]
  - `/Nebulux/noteoff` [note]
  - `/Nebulux/param_name` [value] for param testing

---

## Future Phase: GUI Controller (PyQt6 + Mido)

### Primary Responsibilities:
1. **Read Faust JSON file**
   - Extract all OSC variables and endpoints
   - Dynamically create numeric sliders/text inputs for each parameter

2. **Build UI**
   - Qt controls mapped to OSC paths
   - MIDI Input Port dropdown
   - OSC IP/port configuration (optional for now)

3. **MIDI Mapping Layer**
   - Receive MIDI via Mido
   - Map CC, aftertouch, pitch bend, breath, etc. to OSC parameters
   - Polyphonic aftertouch support via channel + note mapping

4. **Status Indicators**
   - OSC send status (per parameter)
   - MIDI receive status
   - Dual-light mode (only both lights = successful mapped MIDI→OSC event)

---

## Naming Convention (OSC Paths)
- All parameters exposed under:
  - `/Nebulux/param_name`
- Notes:
  - `/Nebulux/noteon [note, velocity]`
  - `/Nebulux/noteoff [note]`

---

## Dependencies
- **Faust** (latest)
- **PyQt6**
- **python-osc**
- **mido**
- (optional) **rtmidi** backend for Mido

---

## Next Steps
- [ ] Build `Nebulux.dsp` with all Phase 1 controls and OSC paths
- [ ] Create `test_osc_trigger.py` script to simulate note events and param changes
- [ ] Confirm polyphonic behavior via `faust2jackconsole -osc -polyphony N`
- [ ] Design JSON schema for UI autogen in GUI phase
- [ ] Begin PyQt6 GUI wiring with MIDI/OSC
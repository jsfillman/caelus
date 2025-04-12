# Caelux Mini Faust DSP Components

This directory contains [Faust](https://faust.grame.fr/) DSP implementation files for the Caelux Mini synthesizer. Faust is a functional programming language for real-time signal processing and synthesis.

## Contents

- **caelux_faust.dsp**: Main Faust DSP implementation for the Caelux Mini engine
- **caelux_osc.dsp**: Oscillator-specific DSP implementation
- **caelux_osc.cpp**: Compiled C++ output from the Faust oscillator DSP
- **caelux_osc.dsp.json**: JSON representation of the oscillator DSP architecture

## Purpose

These files provide optimized, low-level DSP implementations that can be compiled and integrated with the Python-based Caelux Mini synthesizer to improve performance for critical audio components.

## Usage

To compile the Faust DSP files to various targets:

```bash
# Compile to C++
faust -a minimal-effect.cpp -o caelux_osc.cpp caelux_osc.dsp

# Generate JSON architecture file
faust -json caelux_osc.dsp -o caelux_osc.dsp.json
```
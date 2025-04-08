# Caelux Mini: Comprehensive Design Document (v2)

## 1. Overview

Caelux Mini is an advanced FM synthesis engine implemented in Python, designed to create complex, evolving sounds through a hierarchical oscillator architecture. It combines flexible sound design capabilities with intuitive parameter control and a modular approach to synthesis.

## 2. Core Architecture

### 2.1 Oscillator Design

Each oscillator in Caelux Mini is identical in capabilities, regardless of its role as a carrier or operator. Every oscillator includes:

- **Waveform Selection**: Multiple wavetable options (sine, saw, square, formants, etc.)
- **Oscillator Bank**: Variable number of detuned oscillators per voice (1-20)
- **Frequency Control**: Ratio/fixed modes, ramps, envelopes, and randomization
- **Amplitude Control**: ADSR envelope and independent ramping system
- **Filter Section**: Resonant lowpass filter with envelope and ramping
- **Feedback System**: Multiple feedback routing options with variable depth
- **Delay Effects**: Multi-tap stereo delay with independent parameters
- **Stereo Panner**: Assign stereo output to any of the 8 output or modulation buses, with autopanning LFO and width control
- **Bypassable Sections**: Each section (oscillator, freq, amp, filter, delay) can be disabled to save CPU and pass audio through directly



### 2.2 Particle Structure

A "particle" consists of 7 identical oscillators arranged in a binary tree:

- 3 Operators (OP1-OP3): Function primarily as modulators
- 4 Carriers (CAR1-CAR4): Generate the final audio output

```
                       ┌──────────┐
                       │   OP1    │
                       └─────┬────┘
                   ┌─────────┴─────────────────────────────┐
             ┌─────▼─────┐                           ┌─────▼─────┐
             │    OP2    │                           │    OP3    │
             └──────┬────┘                           └─────┬─────┘
        ┌───────────┴────────┐                     ┌───────┴───────────┐
  ┌─────▼─────┐        ┌─────▼─────┐       ┌───────▼─────┐       ┌─────▼─────┐
  │    CA1    │        │    CA2    │       │     CA3     │       │    CA4    │
  └──┬───┬────┘        └──┬──┬─────┘       └───┬──┬──────┘       └─┬───┬─────┘
```

## 3. Oscillator Parameters

Each oscillator contains identical parameter sets across these categories (including new routing and bypass controls):

### 3.1 Oscillator Bank Parameters

- **Wave Type**, **Number of Oscillators**, **Detune Amount**, **Detune Mode**, **Spread**, **Phase Spread**, **Amplitude Distribution**

### 3.2 Frequency Control Parameters

- **Frequency Mode**, **Manual Frequency**, **Coarse/Fine Detune**, **Slew Delay/Time**, **Start Randomization**, **Start/End Slew**, **Frequency Envelope Depth**

### 3.3 Envelope Parameters

- **Frequency ADSR**, **Amplitude ADSR**

### 3.4 Ramp Parameters

- **Amplitude Ramp Delay/Time/Start/End**

### 3.5 Filter Parameters

- **Filter Resonance**, **Ramp Delay/Time/Start/End**

### 3.6 Feedback Parameters

- **Feedback Source** (Off, Pre-Delay, Post-Delay), **Feedback Depth**

### 3.7 Delay Parameters

- **Left/Right Tap Times** (3 each), **Left/Right Feedback**

### 3.8 Panner Parameters

- **Pan Targets**: Up to 2 stereo bus targets (carriers or operators)
- **Width**: Stereo width of output
- **Autopanner LFO**: HarmTable-controlled LFO for stereo movement

### 3.9 Bypass Parameters

- **Bypass Switches** for: Oscillator Bank, Frequency Processing, Amplitude Envelope, Filter, Delay

## 4. Modulation Architecture

### 4.1 Modulation Process

1. Each oscillator generates its own signal
2. The signal flows through its enabled processing chain
3. Operators modulate the frequency of other oscillators via flexible routing
4. Carriers route to configurable output buses (8 total)

### 4.2 Modulation Routing

- Fully flexible modulation matrix: any oscillator can modulate any other (even OP1)
- Default structure follows binary tree, but routing is user-configurable via panner

### 4.3 Signal Flow (Per Oscillator)

```
Oscillator Bank → Frequency Processing → Amplitude Processing →
Filter → Feedback → Delay → Panner → Output/Modulation
```

## 5. Particle Implementation

### 5.1 Particle Parameters

- 3 operators and 4 carriers, each with full parameter sets
- Global parameters: master volume, global effects

### 5.2 Inter-oscillator Communication

- Modulation occurs via frequency input, with routing handled through panner settings
- Oscillators are fully independent except where routing defines relationships

## 6. Multi-Particle System

### 6.1 Particle Organization

- Multiple particles with their own oscillator sets, parameter state, and MIDI input channel
- Default playback mode: unison; optional MPE and polyphonic support

### 6.2 Resource Allocation

- Shared wavetable library
- Parallel processing of particles
- Mixed to final 8-channel bus (or binaural approximation)

## 7. Implementation Approach

### 7.1 Development Phases

- **Phase 1**: Single oscillator with bypass support and full parameter coverage
- **Phase 2**: OP1 → OP2 → CAR1, CAR2 chain
- **Phase 3**: Full 3-op/4-car tree
- **Phase 4**: Multi-particle with 8-channel output

### 7.2 Performance Considerations

- Auto-disable bypassed sections to conserve CPU/memory
- Conditional instantiation of operators based on signal chain needs
- Parallel processing of particles

## 8. User Interface

### 8.1 Main Interface Elements

- **Tab Selector**: Vertical tabs for each oscillator plus Global tab
- **Parameter Panels**: Organized by category with bypass and visual feedback
- **Output Visualizer**: Levels and channel routing display
- **Routing Matrix View**: Dynamic panner routing interface

### 8.2 Parameter Organization

- **Hierarchical Naming**: particle.car1.wave_type, etc.
- **Tabbed Categories**: Waveform, Envelope, Filter, etc.
- **Macros**: Control multiple parameters at once

## 9. Preset System

### 9.1 Format

- YAML-based
- Hierarchical, matching internal parameter structure

### 9.2 Preset Types

- Full particle presets
- Oscillator-level partial presets
- Metadata and version tagging

## 10. Future Extensions

### 10.1 Synthesis and Effects

- Additional oscillator types, filter modes
- Cross-feedback
- Convolution-based spatialization

### 10.2 Interfacing

- OSC and MIDI Learn
- AI Patch Assistant integration
- Audio export

## 11. Technical Requirements

- Python 3.7+
- Pyo DSP library
- PyQt5 GUI
- Multiprocessing for particle parallelism
- 8-channel audio interface or binaural headphone output

## 12. Conclusion

Caelux Mini simplifies high-dimensional sound design by unifying FM, additive, and spatial synthesis into a modular oscillator architecture. Its flexible routing, parameter bypassing, and particle-based design enable CPU-efficient experimentation with complex soundscapes in immersive formats.
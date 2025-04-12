# Caelux

![Caelux Logo](Caelux.png)

Caelux is a distributed additive/FM synthesizer designed for immersive surround sound synthesis and cinematic sound design. It builds upon concepts from Caelus but with a fundamentally different architecture optimized for clustered processing.

## Overview

Caelux uses a **clustered controller-worker model**:

- The **controller** handles:
  - MIDI and OSC input/output
  - Wave file rendering and live audio output
  - A Qt-based local GUI
  - Routing of OSC commands to workers
  - Receiving rendered audio buffers from workers

- The **workers** are responsible for:
  - Receiving and parsing OSC messages from the controller
  - Rendering audio by processing multiple *particles*
  - Each *particle* is a self-contained additive+FM structure with 7 tightly interlinked oscillators

## Architecture

### Oscillator Design

Each oscillator in Caelux is a highly optimized unit with a dedicated processing pipeline:

```
[FM Intensity Mod] → [Frequency/Amplitude Ramp] → [ADSR Envelope] → 
[Harmtable Oscillator] → [Stereo Multitap Delay] → 
[Stereo Panner (LFO-Controlled)] → [Output Stereo Pair]
```

### Particle Structure

Each **particle** is a 7-operator additive+FM unit with operators chained in a nested FM tree:

- **OP1–OP3** are *modulators only* (not heard directly)
- **OP4–OP7** produce the final audio output
- Each output oscillator sends audio to a different stereo pair with spatial panning

## Features

- Distributed audio processing for high-performance synthesis
- Immersive 8-channel surround sound output (7.1 or 7.0.2 format)
- Complex FM and additive synthesis capabilities
- Dynamic spatial positioning of sound elements
- OSC-controlled network architecture

## System Requirements

- Python 3.7+
- pyo audio library for audio processing
- Qt for GUI
- Network capability for controller-worker communication
- Multi-channel audio interface (for surround sound output)

## Documentation

For more detailed information about the architecture and design of Caelux, see the [Design Document](docs/DesignDoc.md).

## Related Projects

- [Caelus](../caelus/README.md) - The original FM synthesis engine
- [Caelux Mini](../caelux-mini/README.md) - A simplified standalone version of Caelux
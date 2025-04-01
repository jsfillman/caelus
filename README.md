# Caelus

Caelus is an advanced, modular FM synthesis engine built with Python and the `pyo` audio processing library. It provides a flexible, high-quality framework for creating complex FM sounds with extensive modulation capabilities.

## Overview

Caelus implements a sophisticated FM synthesis architecture with the following features:

- Multiple operator FM synthesis
- Extensive modulation capabilities with time-varying parameters
- Parameter ramping for dynamic timbral evolution
- MIDI input with monophonic / MPE capabilities and aftertouch support
- Comprehensive GUI controls for all synthesis parameters
- High-quality audio output with proper limiting and 3d spatialization

## Core Components

The synthesis engine is built around these key components:

1. **Operator System**: Independent oscillators that can function as carriers or modulators
2. **Envelope System**: ADSR envelopes for both amplitude and frequency modulation
3. **Ramping System**: Linear segment generators (Linseg) for time-based parameter evolution
4. **MIDI Interface**: Real-time MIDI input with note priority management
5. **GUI System**: Comprehensive control interface for all synthesis parameters

## Architecture

The current architecture supports multiple configurations:

- **MegaPartial**: A complex FM synthesizer with 12 modulators arranged in various FM and AM chains

## Getting Started

### Prerequisites

- Python 3.7+
- pyo audio library
- mido for MIDI handling

### Installation

```bash
pip install pyo mido
```

### Running the Synthesizer

To start the basic synthesizer:

```bash
python mega-partial-2op.py
```

For the more advanced implementation:

```bash
python mega-partial.py
```

## Parameter Guide

### Operator Controls

Each operator has the following parameters:

- **Ratio**: The frequency ratio relative to the carrier frequency

- **Index**: The modulation depth (how much this operator affects others)

- **Frequency Offset**: Static offset in Hz added to the operator's frequency

- **Envelope Controls**: Attack, Decay, Sustain, Release for both amplitude and frequency

- Ramp Parameters

  :

  - Frequency Ramp: Start value, end value, and duration
  - Amplitude Ramp: Start value, end value, and duration

- **Delay**: Time delay before envelope triggering

### FM Routing

The operators are arranged in a serial configuration:

- Series: Op1 → Op2 → Carrier

## Development Roadmap

### 1. Server Capabilities

- Implement OSC (Open Sound Control) server functionality
- Create network-accessible endpoints for remote control
- Support for remote MIDI input over network
- Parameter state saving and loading

### 2. Remote Control Interfaces

- TouchOSC layout design
- Lemur interface implementation
- WebSocket API for browser-based control

### 3. Custom GUI

- Develop Svelte + Tailwind interface
- Design intuitive parameter visualization
- Implement preset management system
- Create visual feedback for modulation activity

### 4. Extended Features

- Multiple voice polyphony via multi-channel MPE
- Additional synthesis algorithms by adding mulitple "mega partials" per channel
- Effects processing chain
- Sample recording and export

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

[License details here]

## Acknowledgments

- Built with the powerful pyo audio processing library
- Inspired by classic FM synthesizers like the Yamaha DX7 and modern FM implementations
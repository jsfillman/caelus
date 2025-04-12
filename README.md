# Caelus Synthesizer Suite

![Caelus Logo](Caelus.png)

This repository contains a collection of experimental software synthesizers built primarily with Python, using libraries like `pyo` for audio processing. Each directory represents a different synthesizer or variant with its own unique features and capabilities.

## Projects in this Repository

### Caelus

A modular FM synthesis engine with extensive modulation capabilities. Features multiple operator FM synthesis, parameter ramping, MIDI input with MPE support, and high-quality audio output with 3D spatialization.

[View Caelus README](caelus/README.md)

### Caelux

A distributed additive/FM synthesizer designed for immersive surround sound synthesis and cinematic sound design. Uses a clustered controller-worker architecture with "particles" consisting of 7 FM/additive oscillators per unit.

[View Caelux Documentation](caelux/docs/DesignDoc.md)

### Caelux Micro

An ultra-lightweight version of Caelux designed for minimal resource usage while retaining core functionality. Provides essential FM and additive synthesis capabilities with basic UI controls and can be integrated into the larger Caelux ecosystem or run standalone.

[View Caelux Micro README](caelux-micro/README.md)

### Caelux Mini

A standalone, simplified version of the larger Caelux synthesizer focusing on high-quality sound design using a combination of FM and additive synthesis with multichannel routing for immersive sound.

[View Caelux Mini README](caelux-mini/README.md)

### Octolux

A modular 8-oscillator wavetable synthesizer designed for immersive sound design and real-time control. Features per-oscillator detuning, envelope shaping, and filter modulation, all routed independently for surround/spatial mixing.

[View Octolux README](octolux/README.md)

## Getting Started

Each synthesizer has its own dependencies and setup instructions. Please refer to the individual README files in each directory for specific installation and usage instructions.

## Requirements

Generally, these synthesizers require:
- Python 3.7+ (3.10+ for some projects)
- pyo audio library
- Various GUI libraries (PyQt5/PyQt6)
- MIDI handling libraries (mido)
- Audio routing capabilities (often using Blackhole or similar virtual audio interfaces)

## License

[License details to be added]
# Caelux Worker Libraries

This directory contains library modules used by the Caelux worker component. These libraries implement the core DSP and synthesis functionality.

## Modules

- **delay.py**: Implements various delay-based effects
  - Multi-tap delay lines
  - Feedback routing
  - Time/pitch synchronization

- **oscilator.py**: Core oscillator implementations
  - FM and additive synthesis algorithms
  - Wavetable management
  - Frequency and amplitude modulation

- **particle.py**: Implements the particle synthesis structure
  - Management of multiple oscillators as a single entity
  - Routing and connection logic for oscillator chains
  - Parameter management and modulation mapping

## Design Philosophy

These libraries are optimized for performance, as they handle the real-time audio processing tasks. They use techniques like vectorized operations, pre-computed tables, and buffer-based processing to minimize CPU usage while maintaining high audio quality.
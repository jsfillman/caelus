# Caelux Worker

This directory contains the worker component of the Caelux distributed synthesizer system. Workers handle the actual audio synthesis processing, receiving commands from the controller and sending back rendered audio.

## Overview

The worker is responsible for:

- Receiving OSC commands from the controller
- Rendering audio using "particles" (collections of oscillators)
- Processing audio with effects
- Sending rendered audio buffers back to the controller
- Managing its own resource allocation and processing pipeline

## Components

- **worker.py**: Main worker implementation
- **lib/**: Library modules for specific worker functions
  - **delay.py**: Delay effect processing
  - **oscilator.py**: Core oscillator implementations
  - **particle.py**: Particle (multi-oscillator) implementation

## Architecture

Each worker operates independently and can process multiple particles simultaneously. Workers are designed to be distributed across multiple CPU cores or even separate machines in a networked configuration, allowing the Caelux system to scale its processing power as needed.
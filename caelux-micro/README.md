# Caelux Micro

![Caelux Micro](Caelux-micro.png)

A streamlined version of the Caelux synthesizer, designed for minimal resource usage while retaining core functionality. This implementation serves as a compact module that can be integrated into the larger Caelux distributed architecture.

## Overview

Caelux Micro provides:

- Essential FM and additive synthesis capabilities
- Basic UI controls for sound design
- Compatible patch format with the full Caelux
- Lower resource consumption for deployment on resource-constrained systems

## Components

- **main.py**: Main application entry point
- **settings.py**: System and audio configuration settings
- **synth_ui.py**: Simplified user interface implementation
- **wavetables.py**: Wavetable definitions and utilities
- **caelux-mini-design-doc.md**: Design documentation
- **last_patch.yaml**: Example/default patch configuration

## Usage

This module can be run standalone or integrated into the larger Caelux ecosystem.

To run standalone:

```bash
python main.py
```

When used within the Caelux architecture, this module is typically instantiated by the controller component as needed.
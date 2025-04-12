# Caelux Controller

This directory contains the controller component of the Caelux distributed synthesizer system. The controller handles user interfaces, input processing, and communication with worker nodes.

## Overview

The controller is responsible for:

- Processing incoming MIDI and OSC messages
- Providing the graphical user interface (GUI)
- Routing control messages to worker nodes
- Managing audio playback and file export
- Coordinating the overall system state

## Components

- **controller.py**: Main controller implementation
- **lib/**: Library modules for specific controller functions
  - **audio.py**: Audio interface handling
  - **gui.py**: Qt-based GUI implementation
  - **midi.py**: MIDI message processing
  - **osc2way.py**: Bidirectional OSC communication with workers

## Architecture

The controller follows a central command pattern, where it acts as the hub for all user interactions and distributes processing tasks to the worker nodes. It receives processed audio back from workers and manages final output routing and mixing.
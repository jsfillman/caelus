# Caelux Controller Libraries

This directory contains library modules used by the Caelux controller component. These libraries handle specific functional areas of the controller.

## Modules

- **audio.py**: Handles audio interface initialization, management, and routing
  - Audio device selection and configuration
  - Stream handling for playback and recording
  - Buffer management for audio I/O

- **gui.py**: Implements the Qt-based graphical user interface
  - Main application window and UI layout
  - Widget creation and management
  - Signal/slot connections for UI events

- **midi.py**: Provides MIDI input and output processing
  - MIDI device detection and selection
  - Message parsing and handling
  - Mapping MIDI data to synthesis parameters

- **osc2way.py**: Facilitates OSC communication with worker nodes
  - OSC server for receiving messages from workers
  - OSC client for sending messages to workers
  - Message formatting and routing logic

## Usage

These libraries are imported by the main controller module and should not typically be used directly outside the controller context.
# Caelus: OSC Polyphonic Router for Synthesizers

<img src="Caelus.png" alt="Caelus Logo" width="300"/>

A polyphonic MIDI-to-OSC bridge and router system that allows distributing MIDI events across multiple synthesizer instances to achieve polyphony, even with monophonic synths.

## Overview

This project solves a common limitation with synthesizers that use OSC: while some have internal polyphony support, their OSC interfaces often don't expose this functionality. Caelus allows you to:

1. Convert MIDI messages to OSC commands
2. Route note events to multiple synth instances running on different ports
3. Handle sustain pedal, modulation wheel, and other MIDI controllers properly
4. Support voice allocation with highest-note priority and voice stealing

## Simple Data Flow

Caelus maintains a clean and straightforward data flow:

```
    ┌─────────┐       ┌─────────┐       ┌─────────┐       ┌─────────┐
    │  MIDI   │       │  MIDI   │       │   OSC   │       │  Synth  │
    │ Device  │ MIDI  │   OSC   │  OSC  │ Router  │  OSC  │ Voices  │
    │(Keyboard)│ ────►│ Bridge  │ ────► │(Caelus) │ ────► │(1,2,3,4)│
    └─────────┘       └─────────┘       └─────┬───┘       └─────────┘
                                            ▲ │
                                            | │ OSC
                                            | ▼
                                         ┌────────┐
                                         │TouchOSC│
                                         │  &  UI │
                                         └────────┘
```

- **Bidirectional Communication**: UI components can both send commands to the router and receive status updates
- **Simple Flow**: MIDI → OSC → Router → Synth Voices
- **Flexible Setup**: Works with any MIDI device and any OSC-compatible synthesizer

## Installation

### Prerequisites

- [Python 3.6+](https://www.python.org/downloads/)
- Python dependencies:
  - mido
  - python-osc (pythonosc)
  - pyyaml

### Installing Python Dependencies

```bash
pip install mido python-osc pyyaml
```

## Configuration

Edit a YAML configuration file (like `voices.yaml`) to configure the voice instances:

```yaml
# Global settings
settings:
  synth_name: simple  # Name of the synth
  synth_host: 127.0.0.1  # Host where synth instances are running

# Voice definitions
voices:
  - id: 0
    port: 5510  # Base port
  - id: 1
    port: 5610  # Base port + 100
  - id: 2
    port: 5710  # Base port + 200
  - id: 3
    port: 5810  # Base port + 300
```

Each voice corresponds to a separate synth instance running on a different port.

## Usage

### 1. Launch Synth Instances

Use the `launch_poly_synth.sh` script to start multiple instances of your synth:

```bash
./launch_poly_synth.sh
```

This script starts each instance on the ports specified in your configuration file.

### 2. Start the OSC Router

```bash
python osc_router.py --config voices.yaml
```

This starts the OSC router, which listens for messages from the MIDI-OSC bridge and routes them to the appropriate synth instance.

Available options:
```
-c, --config      Path to config file (JSON or YAML)
-p, --port        OSC port to listen on (default: 9000)
-v, --voices      Number of voices to create if no config (default: 4)
-s, --start-port  Starting port for auto-generated voices (default: 5510)
--ui-host         Host for sending UI feedback
--ui-port         Port for sending UI feedback
```

### 3. Start the MIDI-OSC Bridge

```bash
python midi_osc.py [router_port]
```

Where `router_port` is the port where the OSC router is listening (default: 9000).

The script will prompt you to select a MIDI input device, then begin sending MIDI events to the router as OSC messages.

## Features

- **Polyphonic Voice Allocation**: Allocates MIDI notes to available voices with voice stealing
- **Sustain Pedal Support**: Properly handles notes held by sustain pedal
- **Modulation Wheel**: Maps to filter cutoff by default
- **Expression Pedal**: Also maps to filter cutoff with independent control
- **Pitch Bend**: Affects active notes uniformly
- **Aftertouch**: Supports both channel and polyphonic aftertouch
- **UI Feedback**: Both sends status to and receives commands from UI clients via OSC

## Architecture

The codebase is organized into several modular components, each with a single responsibility:

```
lib/
  ├── common/        # Shared utilities and constants
  ├── midi_osc/      # MIDI to OSC bridge components
  └── osc_bridge/    # OSC routing system
      ├── router.py       # Main router implementation
      ├── voice.py        # Voice instance management
      └── voice_manager.py # Voice allocation and control
```

### Key Classes

- **OSCRouter**: Handles incoming messages and routes them to appropriate voices
- **VoiceManager**: Manages allocation of voices for polyphonic playing
- **Voice**: Represents a single synth voice instance
- **NoteTracker**: Tracks note allocation state and sustain information
- **UIBridge**: Handles bidirectional communication with UI clients via OSC
- **ConfigLoader**: Loads and parses configuration files

## OSC Message Format

The system uses the following OSC message format:

- Note on: `/router/note_on [note] [velocity]`
- Note off: `/router/note_off [note]`
- CC messages: `/router/cc [cc_num] [value]`
- Pitch bend: `/router/pitch_bend [value]`
- Aftertouch: `/router/aftertouch [value]`
- Poly aftertouch: `/router/poly_aftertouch [note] [value]`
- All notes off: `/router/all_notes_off`
- Parameter setting: `/router/param [param_name] [value]`
- Variable getting/setting: `/router/get [var_path]` and `/router/set [var_path] [value]`

## UI Integration

Caelus supports bidirectional communication with UI clients:

1. **Router → UI**: The router sends status updates, parameter changes, and voice allocation info to registered UIs
2. **UI → Router**: UIs can send commands to control the router, change parameters, or trigger actions

To register a UI client with the router, send an OSC message to:
```
/router/register_ui [host] [port]
```

## Limitations

- The voice allocation currently uses a simple highest-note priority algorithm
- All synth instances must use the same OSC message format

## License

This project is open source under the MIT license.

## Acknowledgements

- [python-osc](https://github.com/attwad/python-osc)
- [mido](https://github.com/mido/mido) 

# MIDI-OSC Polyphonic Router for Faust

A polyphonic MIDI-to-OSC bridge and router system that allows distributing MIDI events across multiple Faust synthesizer instances to achieve polyphony, even with monophonic synths.

## Overview

This project solves a common limitation with Faust synthesizers: while Faust has internal polyphony support, its OSC interface doesn't expose this functionality. This system allows you to:

1. Convert MIDI messages to OSC commands
2. Route note events to multiple Faust instances running on different ports
3. Handle sustain pedal, modulation wheel, and other MIDI controllers properly
4. Support voice allocation with highest-note priority

## Installation

### Prerequisites

- [Python 3.6+](https://www.python.org/downloads/)
- [Faust](https://faust.grame.fr/downloads/) (2.5 or higher recommended)
- Python dependencies:
  - mido
  - python-osc (pythonosc)
  - pyyaml

### Installing Python Dependencies

```bash
pip install mido python-osc pyyaml
```

### Compiling Faust Synth

1. Place your Faust DSP file in the project directory (see `simple.dsp` for an example)
2. Compile it using faust2jackconsole:

```bash
faust2jackconsole -osc simple.dsp
```

This creates a standalone executable that can receive OSC messages.

## Configuration

Edit `voices.yaml` to configure the voice instances:

```yaml
# Global settings
settings:
  synth_name: simple  # Name of the Faust synth
  synth_host: 127.0.0.1  # Host where Faust instances are running

# Voice definitions
voices:
  - id: voice1
    port: 5510  # Base port
  - id: voice2
    port: 5610  # Base port + 100
  - id: voice3
    port: 5710  # Base port + 200
  - id: voice4
    port: 5810  # Base port + 300
```

Each voice corresponds to a separate Faust instance running on a different port.

## Usage

### 1. Launch Faust Instances

Use the `launch_poly_synth.sh` script to start multiple instances of your Faust synth:

```bash
./launch_poly_synth.sh
```

This script starts each instance on the ports specified in your `voices.yaml` file.

### 2. Start the OSC Router

```bash
python osc_router.py --config voices.yaml
```

This starts the OSC router, which listens for messages from the MIDI-OSC bridge and routes them to the appropriate Faust instance.

### 3. Start the MIDI-OSC Bridge

```bash
python 01-midi-osc.py [router_port]
```

Where `router_port` is the port where the OSC router is listening (default: 9000).

The script will prompt you to select a MIDI input device, then begin sending MIDI events to the router as OSC messages.

## Features

- **Polyphonic Voice Allocation**: Allocates MIDI notes to available voices
- **Sustain Pedal Support**: Properly handles notes held by sustain pedal
- **Modulation Wheel**: Maps to filter cutoff by default
- **Expression Pedal**: Also maps to filter cutoff with independent control
- **Pitch Bend**: Affects active notes uniformly
- **Aftertouch**: Supports both channel and polyphonic aftertouch

## How It Works

1. The MIDI-OSC bridge (`01-midi-osc.py`) converts MIDI messages to OSC messages:
   - Note on → `/router/note_on [note] [velocity]`
   - Note off → `/router/note_off [note]`
   - CC messages → `/router/cc [cc_num] [value]`

2. The OSC router (`osc_router.py`) receives these messages and:
   - Allocates notes to available voices
   - Manages sustain, modulation, and other controllers
   - Forwards messages to the correct Faust instance

3. Multiple Faust instances, each running on its own port, receive and process the OSC messages.

## Limitations

- The voice allocation currently uses a simple highest-note priority algorithm
- All Faust instances must use the same OSC message format

## License

This project is open source under the MIT license.

## Acknowledgements

- [Faust](https://faust.grame.fr/) by GRAME-CNCM
- [python-osc](https://github.com/attwad/python-osc)
- [mido](https://github.com/mido/mido) 
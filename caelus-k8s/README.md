# Caelus K8s

A distributed polyphonic synthesizer designed to run in a Kubernetes environment.
"If Brian Eno and Kelsey Hightower had a baby synth, it’d be Caelus K8s."

![Caelus K8s Architecture](./Caelus-K8s.png)

## Overview

Caelus K8s separates MIDI control and audio generation across a controller and multiple worker nodes, with each worker generating one note at a time. The system uses Open Sound Control (OSC) for sending control messages and Real-time Transport Protocol (RTP) for returning audio streams.

## Features

- Controller receives MIDI input and routes notes to workers via OSC
- Workers generate sine waves based on note commands and stream audio back via RTP
- Controller mixes and plays audio from all workers
- Multi-node support for polyphony
- Kubernetes deployment ready

## Installation

### Local Development

1. Create a virtual environment:
   ```
   python -m venv caelus-venv
   ```

2. Activate the virtual environment:
   ```
   source caelus-venv/bin/activate
   ```

3. Install dependencies:
   ```
   pip install python-osc pyo mido python-rtmidi numpy
   ```

### Kubernetes Deployment

For Kubernetes deployment, see the [Kubernetes README](kubernetes/README.md).

## Usage

First, activate the virtual environment:
```
source venv/bin/activate
```

### Start the Controller

```
./caelus controller
```

The controller:
- Uses JACK audio with client name "controller"
- Prompts for MIDI input device selection
- Listens for workers to register

### Start Workers

Start the first worker:
```
./caelus worker
```

Start additional workers (use different ports and client names):
```
./caelus worker --port 9001 --jack-client-name worker2
./caelus worker --port 9002 --jack-client-name worker3
```

Each worker:
- Registers with the controller
- Generates audio for notes assigned by the controller
- Streams audio via JACK

### Additional Options

#### Test Notes

Send test notes through the controller:
```
./caelus controller --test
```

#### Run Without Audio Output

Run in offline mode (disable audio):
```
./caelus controller --offline
```

#### Disable MIDI Selection

Skip the MIDI device selection prompt:
```
./caelus controller --no-select-midi
```

#### Disable JACK Audio

Use socket mode instead of JACK:
```
./caelus controller --no-jack
```

## Architecture

- **Controller**: Receives MIDI, sends OSC, receives RTP, mixes audio
- **Worker**: Receives OSC, generates audio, sends RTP

### Communication Flow

1. Controller receives MIDI note
2. Controller selects available worker
3. Controller sends OSC message (note, velocity, etc.) to worker
4. Worker synthesizes PCM sine wave
5. Worker sends RTP stream with audio
6. Controller receives, mixes, and plays back audio

## Future Plans

- Advanced synthesizer capabilities (FM, filters, etc.)
- Web-based patch editor
- Dynamic worker allocation
- Multiple synth voices per worker

## License

All Rights Reserved

This project and its code are provided for non-commercial use only. No permission is granted for commercial use, distribution, or modification without explicit written authorization.

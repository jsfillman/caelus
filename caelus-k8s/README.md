# Caelus K8s

A distributed polyphonic synthesizer designed to run in a Kubernetes environment.

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

### Start a Worker

```
./caelus worker --ip 0.0.0.0 --port 9000
```

### Start the Controller

```
./caelus controller --worker-ip 127.0.0.1 --worker-port 9000 --rtp-port 5000
```

### Run Test Notes

```
./caelus controller --worker-ip 127.0.0.1 --test
```

### Run Without Audio Output

```
./caelus controller --worker-ip 127.0.0.1 --offline --test
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
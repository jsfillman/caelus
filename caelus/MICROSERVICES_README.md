# Caelus Microservice Architecture

This document describes the microservice architecture of the Caelus synthesizer system, which has been redesigned to address startup order issues and provide a more robust and flexible architecture.

## Overview

The microservice architecture consists of two main services:

1. **Router Service**: Handles OSC message routing to synth voices, loads patches, and launches synth processes
2. **MIDI Service**: Handles MIDI input and converts it to OSC messages for the router

Each service exposes two interfaces:
- **OSC Interface**: Traditional UDP-based OSC server
- **HTTP API**: REST API for service discovery, status, and control

## Automatic Functionality

The microservices include several automatic behaviors:

1. **Service Discovery**: Services automatically discover each other, regardless of startup order
2. **MIDI Auto-Connection**: The MIDI service automatically connects to the first available MIDI input if none is specified
3. **Preset Loading**: The Router service loads a preset (default: "00 - Simple Mono") which includes voice configuration
4. **Synth Launching**: The Router service launches synth processes when a synth binary is found in the preset directory

## Port Conventions

The services use a consistent port numbering scheme:

- **OSC Ports**: 9000-9010 (Router on 9000, MIDI on 9001)
- **HTTP API Ports**: 9100-9110 (Router on 9100, MIDI on 9101)

## Service Discovery

Services automatically discover each other by:
1. Scanning the configured port range (9000-9010) on startup
2. Attempting to connect to the HTTP API of each potential service
3. Registering themselves with discovered services

This means the services can be started in any order and will automatically find each other.

## Starting the Services

### All-in-One Launcher

The easiest way to start both services is with the launcher script:

```bash
./run_microservices.py
```

Optional arguments:
- `--router-port PORT`: Set the Router OSC port (default: 9000)
- `--midi-port PORT`: Set the MIDI service OSC port (default: 9001)
- `--config FILE`: Path to voice configuration file
- `--preset NAME`: Preset name to load (default: "00 - Simple Mono")
- `--midi-input PORT`: MIDI input port to connect to (auto-connects if not specified)

Example with custom configuration:
```bash
./run_microservices.py --preset "01 - Poly" --midi-input "IAC Driver Bus 1"
```

### Starting Services Individually

Router Service:
```bash
./router_service.py --osc-port 9000 --preset "00 - Simple Mono"
```

MIDI Service:
```bash
./midi_service.py --osc-port 9001 --router-port 9000 --router-name router
```

## API Endpoints

### Common Endpoints (Both Services)

- `GET /api/info`: Basic service information and status
- `GET /api/health`: Simple health check
- `GET /api/version`: Version information
- `GET /api/services`: List of discovered services
- `POST /api/register`: Register another service
- `POST /api/shutdown`: Gracefully shutdown the service
- `POST /api/restart`: Restart the service

### Router Service Endpoints

- `GET /api/voices`: List configured voices
- `GET /api/handlers`: List registered OSC message handlers
- `POST /api/note`: Send a test note via API
- `POST /api/all_notes_off`: Send all-notes-off message
- `POST /api/system`: Send a system command to all synths

### MIDI Service Endpoints

- `GET /api/midi/ports`: List available MIDI ports
- `POST /api/midi/select_port`: Select a MIDI port
- `GET /api/midi/activity`: Get MIDI activity statistics
- `POST /api/midi/send_note`: Send a MIDI note through the MIDI port (for testing)

## Example: Interacting with the API

### Get Service Info
```bash
curl http://localhost:9100/api/info
curl http://localhost:9101/api/info
```

### List Available MIDI Ports
```bash
curl http://localhost:9101/api/midi/ports
```

### Select a MIDI Port
```bash
curl -X POST -H "Content-Type: application/json" -d '{"port_name": "IAC Driver Bus 1"}' http://localhost:9101/api/midi/select_port
```

### Send a Test Note
```bash
curl -X POST -H "Content-Type: application/json" -d '{"note": 60, "velocity": 100, "duration": 500}' http://localhost:9101/api/midi/send_note
```

Via Router:
```bash
curl -X POST -H "Content-Type: application/json" -d '{"note": 60, "velocity": 0.8, "duration": 1.0}' http://localhost:9100/api/note
```

### Get Voice Information
```bash
curl http://localhost:9100/api/voices
```

## Benefits of the Microservice Approach

1. **Startup Order Independence**: Services can be started in any order
2. **Self-Healing**: Services automatically discover each other
3. **Isolation**: Each service can be debugged, restarted, or upgraded independently
4. **Observability**: HTTP API provides visibility into service state
5. **Flexibility**: New services can be added without changing existing ones
6. **Extensibility**: Easy to add new functionality through API endpoints

## Troubleshooting

1. **Check Service Status**
   ```bash
   curl http://localhost:9100/api/health
   curl http://localhost:9101/api/health
   ```

2. **Discover Services**
   ```bash
   curl http://localhost:9100/api/services
   ```

3. **Restart a Service**
   ```bash
   curl -X POST http://localhost:9100/api/restart
   ```

4. **Send All-Notes-Off**
   ```bash
   curl -X POST http://localhost:9100/api/all_notes_off
   ```

5. **Reset Synth Voices**
   ```bash
   curl -X POST -H "Content-Type: application/json" -d '{"command": "reset"}' http://localhost:9100/api/system
   ```

## Design Approach

This microservice implementation uses two complementary approaches:

1. **Service Discovery Layer**: New code that provides all the service discovery, HTTP API, and microservice functionality.

2. **Core Functionality**: Reused from the existing Caelus codebase:
   - The `Voice` and `VoiceManager` classes from `lib/osc_bridge/voice.py` and `lib/osc_bridge/voice_manager.py`
   - MIDI message handling logic from `lib/midi_osc/midi_worker.py`
   - Preset loading and synth launching logic similar to `debug_router.py`

This hybrid approach ensures that all existing functionality (including velocity, polyphonic aftertouch, and other features) is preserved, while adding the benefits of the microservice architecture.

## API Extensions

Future versions will extend the API with:

1. **Full MIDI Control**: Additional endpoints for all MIDI controllers
2. **Voice Management**: Endpoints for voice allocation strategies
3. **Remote Control**: Control of all synth parameters via API 
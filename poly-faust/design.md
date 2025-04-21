# Hot-Swappable Synth Router: Design Document

## Overview
This component is a central OSC-based voice and parameter router designed to enable polyphony, sustain handling, and modular synthesis swapping in the Caelux/Octolux 2.0 architecture. It sits between MIDI/OSC inputs and the actual synthesis engines (Faust, Pyo, etc.).

## Primary Goals
- Enable polyphony for OSC-controlled synths (like Faust, which lacks built-in OSC polyphony).
- Manage note and sustain state centrally.
- Route OSC messages to multiple synth instances.
- Allow hot-swapping synth engines (Faust, Pyo, etc.)
- Generate GUI or TouchOSC interface based on Faust JSON metadata.

---

## Architecture
```
[MIDI Input] ---> [MIDI-OSC] ---> [OSC Synth Router]
                                   ├─> [Faust Voice 1 (OSC)]
                                   ├─> [Faust Voice 2 (OSC)]
                                   ├─> [Faust Voice 3 (OSC)]
                                   └─> [Pyo Voice N (OSC)]
```

---

## Components

### 1. MIDI-OSC (Modified)
- Sends simplified OSC messages to the router instead of directly to synths.
- Messages:
  - `/note_on <note> <velocity>`
  - `/note_off <note>`
  - `/sustain <0|1>`
  - (Future) `/pitchbend`, `/channel_pressure`, etc.

### 2. OSC Synth Router (New)
Responsible for:
- Maintaining current note state
- Sustain pedal behavior
- Allocating/deallocating voices
- Translating standard OSC paths (`/freq`, `/gate`, `/gain`) to per-instance messages

#### Subcomponents:
- **Voice Manager**
  - Round-robin allocator (initial)
  - Per-voice state (note, velocity, is_active)
  - Voice stealing (future)

- **Sustain Manager**
  - Tracks notes held during sustain
  - Defers note-off until sustain=0

- **OSC Translator**
  - Sends translated messages to assigned synth ports
  - Maintains mapping of voice_id -> port

- **GUI/TouchOSC Generator** (Optional)
  - Reads Faust JSON
  - Exposes matching control endpoints to TouchOSC or web GUI

### 3. Synth Instances
- Multiple Faust or Pyo processes, each running monophonic
- Identified by port (e.g., 5510, 5511, ...)
- Configurable via external config file (e.g., YAML or JSON)

---

## Message Format

### Incoming to Router (from MIDI-OSC):
```
/note_on    <int note> <float velocity>
/note_off   <int note>
/sustain    <0|1>
```

### Outgoing from Router (to synth):
```
/freq       <Hz>
/gate       <0|1>
/gain       <0.0-1.0>
```

---

## Config Example (voices.json or YAML)
```yaml
voices:
  - id: voice1
    port: 5510
  - id: voice2
    port: 5511
  - id: voice3
    port: 5512
```

---

## Future Extensions
- Add support for multichannel audio routing
- Group voices into patches and dynamically load JSON or YAML descriptions
- Enable real-time switching between Faust and Pyo
- Support MPE and per-channel modulation
- Implement OSC-to-MIDI bridge for external hardware control

---

## Next Steps
1. Modify `midi-osc.py` to emit simplified OSC events to the router
2. Build `osc_router.py` with:
   - OSC listener
   - Note allocator + sustain manager
   - Per-synth OSC sender
3. Create config file format for voice list
4. Test with multiple `faust2jack -osc` instances
5. Add optional GUI JSON reader and routing



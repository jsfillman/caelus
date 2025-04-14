# **Caelus K8s: MVP Design Document**

## **1. Overview**

**Caelus K8s** is a distributed polyphonic synthesizer designed to run in a Kubernetes environment. It separates MIDI control and audio generation across a controller and multiple worker nodes, each generating one note at a time. The MVP focuses on real-time sine wave generation using Pyo, with low-latency control over OSC and audio transport via RTP.

------

## **2. Goals**

- Create a scalable, distributed polyphonic synth.
- Use OSC for control signals, RTP for returning audio.
- Build on Kubernetes for orchestration and replica scaling.
- Generate audio using Pyo.
- Achieve millisecond-grade latency for control and audio sync.

------

## **3. Architecture**

### **3.1 Components**

| Component            | Role                                                         |
| -------------------- | ------------------------------------------------------------ |
| **Controller**       | Receives MIDI, sends OSC, receives RTP, mixes audio          |
| **Worker (replica)** | Receives OSC, generates note as PCM audio with timestamp, sends audio via RTP |

### **3.2 Communication Flow**

1. Controller receives MIDI note.
2. Controller selects available worker.
3. Controller sends OSC message (note, velocity, etc.) to worker.
4. Worker synthesizes PCM using Pyo.
5. Worker sends RTP stream with audio and timestamp.
6. Controller buffers, mixes, and plays back audio.

------

## **4. Protocols**

| Data                  | Protocol                           | Notes                               |
| --------------------- | ---------------------------------- | ----------------------------------- |
| MIDI Input            | Any local (e.g., `mido`, `rtmidi`) | USB or virtual MIDI                 |
| Control (note on/off) | OSC over UDP                       | Simple, efficient                   |
| Audio Streaming       | RTP over UDP                       | Includes timestamp for alignment    |
| Time Sync             | NTP or PTP                         | Needed for accurate audio alignment |

------

## **5. Deployment**

### **Kubernetes Structure**

- **1 Controller Pod**
- **8 Worker Pods** (adjustable for polyphony)
- Optional: ConfigMap or Helm `values.yaml` for note routing and RTP target IP.

### **Service Layout**

- Workers expose:
  - OSC UDP port (e.g., `9000`)
  - RTP UDP port (e.g., `5004`)
- Controller connects to each worker's OSC port and listens for RTP from all workers.

------

## **6. Audio System**

### **Worker Side**

- JACK audio for professional low-latency audio.
- Each note generates:
  - Sine wave oscillator (eventually expandable to FM/ADSR).
  - Continuous audio stream.
  - Optional fallback to Pyo or PyAudio if JACK is unavailable.

### **Controller Side**

- Receives audio streams from all workers via JACK.
- Automatic connection to workers' output ports.
- Mixes all inputs into stereo output.
- MIDI input with interactive device selection.
- JACK client always named "controller" for consistent routing.

------

## **7. Scaling Plan**

| Future Capability       | Direction                                       |
| ----------------------- | ----------------------------------------------- |
| Multiple Voices per Pod | Run multiple Pyo synths per pod                 |
| FM/Additive Support     | Extend worker patch complexity                  |
| Dynamic Scheduling      | Assign workers to users or synth layers         |
| Audio Routing           | NetJack or JACK2 integration                    |
| GUI                     | TouchOSC frontend or web-based patch controller |

------

## **8. Future Considerations**

- RTP jitter buffer or resync logic for alignment.
- OSC acknowledgment protocol.
- Optional REST API for note events.
- Persistent routing configuration for polyphony logic.
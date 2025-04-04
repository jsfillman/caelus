## 🧠 Claude Prompt Stub: Design & Architecture

Here's a Claude-friendly prompt to expand or refine:

> I'm designing a next-gen additive/FM synthesizer called **Caelux**, derived from my existing synth **Caelus (based on Pyo)** but built for clustered processing and cinematic surround sound.
>
> Here's the architecture:
>
> - The system is a **single-controller, multi-worker cluster**.
> - The **controller** handles:
>   - Incoming MIDI and OSC
>   - GUI (Qt), audio playback, and wave file export
>   - Distributing OSC commands to the workers and receiving audio buffers in return
> - **Workers**:
>   - Receive OSC commands
>   - Render "particles," each consisting of 7 highly optimized FM/additive oscillators
>   - Each oscillator is structured as:
>     `FM INT > Ramp > ADSR > Oscillator > Delay > Panner > Feedback`
>   - Outputs are multichannel surround
>
> Help me document this architecture and evolve it over time. Today, let’s focus only on the oscillator signal flow and how a particle routes its 7 operators to generate 8-channel output.

---

## 📄 Design Document: *Caelux* – A Clustered Cinematic Synthesizer

### Overview

**Caelux** is a distributed additive/FM synthesizer designed for immersive surround sound synthesis, particularly for cinematic sound design. It builds upon concepts from *Caelus*, but with a fundamentally different architecture.

At its core, Caelux uses a **clustered controller–worker model**:

- The **controller** handles:
  - MIDI and OSC input/output
  - Wave file rendering and live audio output
  - A Qt-based local GUI
  - Routing and timing of OSC commands to workers
  - Receiving rendered audio buffers back from workers
- The **workers** are responsible for:
  - Receiving and parsing OSC messages from the controller
  - Rendering audio by processing multiple *particles*
  - Each *particle* is a self-contained additive+FM structure consisting of 7 tightly interlinked oscillators

Each oscillator is highly optimized for parallelism (multiprocessing, Numba, etc.) and has a dedicated processing pipeline.

## 🎛 Oscillator Design: Modular Signal Path

Each **oscillator** in Caelux is a highly optimized, standalone unit responsible for generating and spatializing a single stereo voice. Oscillators are fully parallelizable and leverage `multiprocessing`, `Numba`, and vectorized math where possible.

### 🔁 Signal Chain (Per Oscillator)

```
csharp


CopyEdit
[FM Intensity Mod] 
     ↓
[Frequency/Amplitude Ramp] 
     ↓
[ADSR Envelope] 
     ↓
[Harmtable Oscillator] 
     ↓
[Stereo Multitap Delay] 
     ↓
[Stereo Panner (LFO-Controlled)] 
     ↓
[Output Stereo Pair]
```

### 📦 Component Definitions

| Component                | Description                                                  |
| ------------------------ | ------------------------------------------------------------ |
| **FM Intensity Mod**     | Scalar control of incoming frequency modulation amount from a parent oscillator. |
| **Ramp Generator**       | Independent for frequency and amplitude. Applies linear or exponential transitions (e.g. pitch glides, fade-ins/outs). |
| **ADSR Envelope**        | Extended Attack, Decay, and Sustain stages allow for slow ambient evolutions. |
| **Harmtable Oscillator** | High-resolution wavetable (default sine), optimized for additive and FM usage. |
| **Stereo Delay**         | Multitap, long delay support with feedback per channel. Can simulate echoes, rhythmic accents, or diffusion. |
| **Stereo Panner**        | Uses a harmonic LFO to animate stereo position across assigned output pair. |
| **Feedback Routing**     | Mono send of output back into FM input, enabling feedback modulation. Configurable per oscillator. |

------

## 🌌 Particle Structure: 7-Oscillator FM Network

Each **particle** is a self-contained 7-operator additive+FM unit. Operators are chained to form a nested FM tree with 4 final audio-producing oscillators.

### 🧬 FM Routing Topology

```
OP1 → OP2, OP3 (FM modulation only)
OP2 → OP4, OP6
OP3 → OP5, OP7
```

- **OP1–OP3** are *modulator-only* (not heard directly)
- **OP4–OP7** produce the final audio output

### 🔊 Surround Output Mapping

Each output oscillator sends audio to a stereo pair with spatial panning. Here's the final surround mapping:

| Oscillator | Output Channels | Panning Behavior          | Purpose                               |
| ---------- | --------------- | ------------------------- | ------------------------------------- |
| **OP4**    | Out 1–2         | FL ↔ FR                   | Main stereo anchor                    |
| **OP5**    | Out 3–4         | FL ↔ CL                   | Supports center imaging               |
| **OP6**    | Out 5–6         | FR ↔ CR                   | Balances left-field with right motion |
| **OP7**    | Out 7–8         | Rear → Ceiling (mono pan) | Adds Z-axis dimension; shimmer, lift  |

> 🎧 Total Outputs: 8 channels (7.1 or 7.0.2 without LFE).

Each particle’s outputs can be positioned in surround space statically, dynamically (via panning), or sequenced over time.

------
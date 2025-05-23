# Murnau - Cinematic Synthesizer

A stylish, expressive synthesizer inspired by German Expressionist cinema aesthetics, created with Faust DSP language and controlled through OSC or MIDI.

![Murnau Logo](Murnau.png)

## Overview

Murnau is a German Expressionist-inspired synthesizer system that combines:

- Faust DSP for high-quality, efficient audio processing
- OSC for flexible parameter control
- MIDI for playing notes and controller integration
- PyQt6 for a stylish, cinematic user interface

## Components

The system consists of the following core components:

1. **Synthesizer Engine**: Created with Faust DSP language (`legato_synth.dsp`)
   - Monophonic synthesizer with legato capability
   - Four waveform types: Sine, Triangle, Sawtooth, Square
   - Full ADSR envelope control
   - Expressive playing controls

2. **MIDI Control Bridge**: Translates MIDI to OSC commands (`best_midi.py`)
   - Handles legato note transitions
   - Maps MIDI CC controllers to synth parameters
   - Optimized for expressive playing

3. **User Interface**: A stylish PyQt6 UI inspired by German Expressionism (`murnau_ui.py`)
   - Direct control of all synthesizer parameters
   - Built-in virtual piano keyboard
   - Integrated MIDI device connection
   - Waveform visualization
   - German Expressionist-inspired design

## Usage

### Quick Start (Recommended)

Simply run the startup script which handles everything automatically:

```bash
./start_murnau.sh
```

This script will:
1. Start JACK audio server (with CoreAudio on macOS)
2. Compile and start the Faust synthesizer
3. Launch the Murnau GUI
4. Handle cleanup when you press Ctrl+C

### Manual Setup

If you prefer to start components individually:

1. **Start JACK audio server:**
   ```bash
   # macOS
   jackd -d coreaudio -r 44100 -p 256
   
   # Linux
   jackd -d alsa -r 44100 -p 256
   ```

2. **Compile the Faust synthesizer:**
   ```bash
   faust2jackconsole -osc legato_synth.dsp
   ```

3. **Start the synthesizer:**
   ```bash
   ./legato_synth
   ```

4. **Launch the UI:**
   ```bash
   python murnau_ui.py [synth_name] [osc_port]
   ```
   - Default synth_name: "legato_synth_stereo"
   - Default osc_port: 5510

### MIDI Control

- Connect a MIDI controller using the UI's MIDI section
- Select your MIDI device from the dropdown and click "Enable MIDI"

## MIDI Controller Mappings

- CC1 (Mod wheel): Waveform selection
- CC7: Main volume/gain
- CC73: Attack time
- CC75: Decay time
- CC31: Sustain level
- CC72: Release time

## UI Keyboard Shortcuts

- Z-M keys: Play notes (Z = C4, S = C#4, etc.)
- Mouse: Click piano keys to play notes

## Requirements

- **Faust compiler** (for building the synthesizer DSP)
- **JACK audio system** (for real-time audio processing)
- **Python 3.7+** with the following packages:
  - `PyQt6` (GUI framework)
  - `mido` (MIDI library)
  - `python-osc` (OSC communication)

### Installation

1. Install Faust from [faust.grame.fr](https://faust.grame.fr)
2. Install JACK audio system
3. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Acknowledgments

Inspired by the films of F.W. Murnau and the German Expressionist movement.

## License

MIT License
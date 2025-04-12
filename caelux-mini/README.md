# Caelux Mini Synthesizer

Caelux Mini is an advanced FM synthesis engine implemented in Python, designed for creating complex, evolving sounds through a hierarchical oscillator architecture.

## Overview

Caelux Mini is built as a standalone, simplified version of the larger Caelux synthesizer system. It focuses on high-quality sound design using a combination of:

- FM (Frequency Modulation) synthesis
- Additive synthesis
- Multichannel routing for immersive sound

## Features

- **Hierarchical Oscillator Structure**: Uses "particles" with operators and carriers in a modular tree structure
- **Flexible Routing**: Configurable modulation matrix for complex sound design
- **Multichannel Output**: Support for up to 8 channels of audio (7.1 surround)
- **MIDI Integration**: Full MIDI controller support
- **Modular Design**: Each oscillator has identical capabilities with bypass options 
- **Expandable Architecture**: Designed to scale from simple patches to complex soundscapes

## System Requirements

- **Python 3.7+**
- **PyQt5** for the user interface
- **Pyo** for audio processing
- **Mido** for MIDI handling
- **PyYAML** for patch saving/loading
- Multichannel audio interface (for surround sound output)

## Installation

```bash
# Install required packages
pip install pyqt5 pyo mido pyyaml
```

## Running Caelux Mini

Several startup scripts are available depending on your needs:

```bash
# Standard version
python main.py

# Enhanced version with improved interface
python main_updated.py

# 8-channel surround version
python main_8channel.py

# Launcher with options
python run_caelux.py [--setup] [--reset-audio]

# Audio setup utility
python audio_setup.py
```

## Getting Started

1. Launch the application with one of the commands above
2. In the Global tab:
   - Select your preferred audio device
   - Configure sample rate and buffer size
   - Select a MIDI input device
   - Click "Apply Audio Settings" after changing audio options
3. Use the operator (O1) and carrier (C1, C2) tabs to configure your sound
4. Connect a MIDI controller to play notes

## Oscillator Structure

Each oscillator has the following signal path:

```
Oscillator Bank → Frequency Processing → Amplitude Processing → 
Filter → Feedback → Delay → Output/Modulation
```

With these controls:

- **Oscillator Bank**: Waveform selection, unison, detune, and stereo spread
- **Frequency Control**: Pitch, glide, randomization, and envelope
- **Amplitude**: ADSR envelope and ramping
- **Filter**: Lowpass with resonance and envelope
- **Delay**: Multi-tap stereo delays
- **Routing**: Channel assignment and modulation destinations

## Modulation System

The default modulation structure follows this pattern:

- **OP1** (Operator): Provides modulation signal to CAR1 and CAR2
- **CAR1** and **CAR2** (Carriers): Generate final audio output

This can be customized through the modulation matrix in the interface.

## Troubleshooting

- If audio isn't working, check the Global tab for device selection and try the "Test Audio Channels" button
- For MIDI issues, use the "Refresh MIDI Devices" button and reselect your controller
- If no sound is produced when pressing keys, verify that the oscillator bypass switches are not enabled
- For performance issues, try increasing the buffer size or reducing the number of oscillators

## Advanced Configuration

Several utility scripts are provided for advanced configuration:

- **quad_test.py**: Tests multichannel audio output
- **loopback_test.py**: Tests audio routing via Loopback interfaces
- **check_devices.py**: Displays all available audio devices
- **simple_channel_test.py**: Basic tool for testing individual audio channels

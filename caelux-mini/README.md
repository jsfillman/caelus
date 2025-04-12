# Caelux Mini Synthesizer

Caelux Mini is an advanced FM synthesis engine implemented in Python, designed for creating complex, evolving sounds.

## Recent Updates

The application has been restructured with:

1. A modern tab-based interface
   - Global settings tab for audio and MIDI configuration
   - Carrier 1 tab for the synthesizer controls
2. Improved audio and MIDI handling
   - GUI-based audio device selection
   - GUI-based MIDI input selection
   - Better error handling and status reporting
3. Cleaner code organization
   - Separate classes for audio engine, MIDI handling, and UI
   - Improved signal flow between components
   - Better resource management

## Requirements

- Python 3.7+
- PyQt5 for the user interface
- pyo for audio processing
- mido for MIDI handling
- PyYAML for patch saving/loading

## Installation

```
bash



# Install required packages
pip install pyqt5 pyo mido pyyaml
```

## Running the Application

```
bash



# Run the application
python main_updated.py
```

## Usage

1. When the application starts, it will automatically try to:
   - Initialize the audio system with default settings
   - Load the last saved patch
   - Connect to the first available MIDI device
2. Using the Global Settings tab:
   - Select your preferred audio device
   - Configure sample rate and buffer size
   - Select a MIDI input device
   - Click "Apply Audio Settings" after changing audio options
3. Using the Carrier 1 tab:
   - Adjust oscillator parameters
   - Configure frequency and amplitude envelopes
   - Set up filter, feedback, and delay effects
4. Playing sounds:
   - Connect a MIDI keyboard or controller
   - Play notes to trigger the synthesizer
   - Adjust parameters in real-time
5. Your settings are automatically saved when closing the application.

## Future Development

Caelux Mini is under active development with planned features including:

- Support for multiple oscillator "particles" (carriers and operators)
- More modulation options and routing flexibility
- Advanced parameter visualization
- Enhanced preset management
- Support for MIDI mapping and automation

## Troubleshooting

- If you don't hear sound, check the Global tab to ensure the correct audio device is selected
- If MIDI isn't working, try clicking "Refresh MIDI Devices" and selecting your device
- For performance issues, try increasing the buffer size or reducing the number of oscillators
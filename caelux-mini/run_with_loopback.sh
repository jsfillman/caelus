#!/bin/bash
# Script to run Caelux Mini with Loopback Audio 2 as the system default audio device

# Check if SwitchAudioSource is installed
if ! command -v SwitchAudioSource &> /dev/null; then
    echo "Error: SwitchAudioSource is not installed."
    echo "Please install it with: brew install switchaudio-osx"
    exit 1
fi

# Save current output device
CURRENT_OUTPUT=$(SwitchAudioSource -c)
echo "Current audio output: $CURRENT_OUTPUT"

# Switch to Loopback Audio 2
echo "Switching to Loopback Audio 2..."
SwitchAudioSource -s "Loopback Audio 2"

# Verify the change
NEW_OUTPUT=$(SwitchAudioSource -c)
echo "New audio output: $NEW_OUTPUT"

# Run the application with the new audio device as default
echo "Starting Caelux Mini..."
python main_updated.py

# After the app exits, switch back to original output
echo "Switching back to $CURRENT_OUTPUT..."
SwitchAudioSource -s "$CURRENT_OUTPUT"
echo "Audio output restored."
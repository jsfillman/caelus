#!/bin/bash
# Launch script for Caelus polyphonic OSC synth system

echo "=== Caelus Polyphonic Synth Launcher ==="
echo "Starting MIDI-OSC Bridge..."
echo "NOTE: Select your MIDI input device when prompted"
echo "      Then select a synth bank to load"
echo ""

# Start the MIDI-OSC bridge with specific port to avoid conflicts
python3 midi_osc.py --port 9001

# The MIDI-OSC bridge will handle process management and cleanup
exit 0 
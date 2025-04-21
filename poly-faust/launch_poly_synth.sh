#!/bin/bash
# Launch script for polyphonic OSC synth

# Configuration
NUM_VOICES=4
BASE_PORT=5510
PORT_INCREMENT=100  # Each instance will get ports X00, X01, X02
FAUST_DSP="simple.dsp" # The Faust DSP file
ROUTER_PORT=9000
CONFIG_FILE="voices.yaml"

echo "=== Polyphonic OSC Synth Launcher ==="
echo "Starting $NUM_VOICES Faust synth instances..."

# Launch Faust synths in background
SYNTH_PIDS=()
for i in $(seq 1 $NUM_VOICES); do
  PORT=$((BASE_PORT + (i-1)*PORT_INCREMENT))
  echo "Starting synth $i on port $PORT (listening), $((PORT+1)) (output), $((PORT+2)) (error)"
  ./simple -port $PORT &
  SYNTH_PIDS+=($!)
  sleep 1 # Give time for each synth to initialize
done

echo "All synth instances started"

# Start OSC Router
echo "Starting OSC Router on port $ROUTER_PORT..."
python3 osc_router.py -c "$CONFIG_FILE" -p "$ROUTER_PORT" &
ROUTER_PID=$!
sleep 2 # Give router time to initialize

# Handle shutdown gracefully (when user presses Ctrl+C)
function cleanup {
  echo ""
  echo "Shutting down..."
  kill $ROUTER_PID 2>/dev/null
  for pid in "${SYNTH_PIDS[@]}"; do
    kill $pid 2>/dev/null
  done
  echo "All processes terminated."
  exit 0
}

trap cleanup INT TERM

# Start MIDI-OSC Bridge in foreground
echo "Starting MIDI-OSC Bridge..."
echo "NOTE: Select your MIDI input device when prompted"
echo ""
python3 02-midi-osc-router.py

# If the MIDI-OSC bridge exits, clean up other processes
cleanup 
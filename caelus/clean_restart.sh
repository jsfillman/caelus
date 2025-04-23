#!/bin/bash
# Script to kill existing OSC processes and restart with a clean state

echo "=== Caelus Clean Restart ==="

# Find and kill any existing Python OSC processes
echo "Checking for existing OSC processes..."
PIDS=$(ps aux | grep "python.*osc_router" | grep -v grep | awk '{print $2}')

if [ -n "$PIDS" ]; then
    echo "Killing existing OSC router processes: $PIDS"
    kill $PIDS
    sleep 1
else
    echo "No existing OSC router processes found."
fi

# Kill any existing stuck note monitors
MONITOR_PIDS=$(ps aux | grep "python.*fix_stuck_notes" | grep -v grep | awk '{print $2}')
if [ -n "$MONITOR_PIDS" ]; then
    echo "Killing existing stuck note monitor processes: $MONITOR_PIDS"
    kill $MONITOR_PIDS
    sleep 1
else
    echo "No existing stuck note monitor processes found."
fi

# Check specific port 9000 (the conflicting one)
PORT_9000=$(lsof -i :9000 | grep -v "PID" | awk '{print $2}')
if [ -n "$PORT_9000" ]; then
    echo "Found process using port 9000: $PORT_9000"
    echo "This port conflicts with OSC router. Trying to kill it..."
    kill $PORT_9000
    sleep 1
fi

# Check if port 9001 is available
PORT_9001=$(lsof -i :9001 | grep -v "PID" | awk '{print $2}')
if [ -n "$PORT_9001" ]; then
    echo "Port 9001 is still in use by PID $PORT_9001."
    echo "You may need to kill this process manually."
    exit 1
fi

# Start the stuck note monitor in the background
echo "Starting stuck note monitor..."
python3 fix_stuck_notes.py &
MONITOR_PID=$!
echo "Stuck note monitor started with PID $MONITOR_PID"

# Start the MIDI-OSC bridge on our new port
echo "Starting MIDI-OSC bridge on port 9001..."
echo "NOTE: Select your MIDI input device when prompted"
echo "      Then select a synth bank to load"
echo ""

python3 midi_osc.py --port 9001

# When MIDI bridge exits, kill the monitor
echo "MIDI-OSC bridge exited, cleaning up..."
if kill -0 $MONITOR_PID 2>/dev/null; then
    echo "Killing stuck note monitor (PID $MONITOR_PID)"
    kill $MONITOR_PID
fi

echo "Clean shutdown complete."
exit 0 
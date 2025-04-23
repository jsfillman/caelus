#!/bin/bash
# Diagnostic launch script with OSC router debugging patch

echo "=== Caelus Debug Launch ==="

# Find and kill any existing Python OSC processes
echo "Checking for existing OSC processes..."
PIDS=$(ps aux | grep "python.*osc_" | grep -v grep | awk '{print $2}')

if [ -n "$PIDS" ]; then
    echo "Killing existing OSC processes: $PIDS"
    kill $PIDS
    sleep 1
else
    echo "No existing OSC processes found."
fi

# Check if ports are available
for PORT in 9001 9200 9300; do
    PORT_USE=$(lsof -i :$PORT | grep -v "PID" | awk '{print $2}')
    if [ -n "$PORT_USE" ]; then
        echo "Port $PORT is in use by PID $PORT_USE."
        echo "Trying to kill it..."
        kill $PORT_USE
        sleep 1
    fi
done

# Start OSC router debugging patch
echo "Starting OSC router debugging patch..."
python3 osc_router_patch.py --listen-port 9300 &
PATCH_PID=$!
echo "OSC router debug patch started with PID $PATCH_PID"

# Start the MIDI-OSC bridge
echo "Starting MIDI-OSC bridge on port 9001..."
echo "NOTE: Select your MIDI input device when prompted"
echo "      Then select a synth bank to load"
echo ""

# Open a terminal with debug output
gnome-terminal --title="OSC Debug Log" -- tail -f osc_debug.log &
LOG_PID=$!

# Start MIDI OSC bridge
python3 midi_osc.py --port 9001 | tee osc_debug.log

# When MIDI bridge exits, clean up
echo "MIDI-OSC bridge exited, cleaning up..."
if kill -0 $PATCH_PID 2>/dev/null; then
    echo "Killing OSC router patch (PID $PATCH_PID)"
    kill $PATCH_PID
fi

if kill -0 $LOG_PID 2>/dev/null; then
    echo "Killing log viewer (PID $LOG_PID)"
    kill $LOG_PID
fi

echo "Debug shutdown complete."
exit 0 
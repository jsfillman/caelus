#!/bin/bash
# Run test with OSC monitor
# This script runs the test_router_fix.py and monitors the OSC messages on port 5510

# Start OSC monitor in the background
python tools/osc_monitor.py 5510 &
MONITOR_PID=$!

# Wait a moment for monitor to start
sleep 1

# Run the test
python tests/test_router_fix.py

# Kill the monitor
kill $MONITOR_PID
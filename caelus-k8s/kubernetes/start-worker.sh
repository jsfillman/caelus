#!/bin/bash
# Start a Jack server in the background
jackd -d dummy -r 44100 -p 1024 &
JACK_PID=$!

# Wait for Jack to start
sleep 2

# Start the Caelus worker
./caelus worker "$@"

# Clean up Jack server on exit
kill $JACK_PID

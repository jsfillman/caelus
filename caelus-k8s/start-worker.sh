#!/bin/bash
# Start a Jack server in the background with netjack
jackd -d net -r 44100 -p 1024 -a ${CONTROLLER_IP} &
JACK_PID=$!

# Wait for Jack to start
sleep 2

# Start the Caelus worker
./caelus worker "$@"

# Clean up Jack server on exit
kill $JACK_PID

#!/bin/bash
# Launch script for polyphonic OSC synth with distributed instances

# Configuration
ROUTER_PORT=9000
CONFIG_FILE="voices.yaml"
FAUST_DSP="simple.dsp" # The Faust DSP file
FAUST_BINARY="./simple" # The compiled Faust binary

echo "=== Polyphonic OSC Synth Launcher ==="

# Function to check if a host is local
is_local_host() {
  local host=$1
  if [[ "$host" == "127.0.0.1" || "$host" == "localhost" || "$host" == "::1" ]]; then
    return 0 # true
  else
    # Check if host matches any local IP
    if ifconfig 2>/dev/null | grep -q "$host"; then
      return 0 # true
    fi
  fi
  return 1 # false
}

# Function to check if remote host is reachable
check_remote_host() {
  local host=$1
  local port=$2
  echo "Checking connection to $host:$port..."
  
  # First try ping to see if host is up
  ping -c 1 -W 1 "$host" >/dev/null 2>&1
  if [ $? -ne 0 ]; then
    echo "⚠️  Warning: Cannot ping $host - host may be down or blocking ICMP"
    return 1
  fi
  
  # Try to connect to the specific port
  if command -v nc >/dev/null 2>&1; then
    # Use nc if available for port check
    nc -z -w 1 "$host" "$port" >/dev/null 2>&1
    if [ $? -ne 0 ]; then
      echo "⚠️  Warning: Cannot connect to $host:$port"
      return 1
    fi
  fi
  
  echo "✅ Remote host $host:$port is reachable"
  return 0
}

# Read the voices.yaml file to get host information
echo "Reading configuration from $CONFIG_FILE..."
if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 is required"
  exit 1
fi

# Extract hosts and ports using Python
HOSTS_AND_PORTS=$(python3 -c "
import yaml
try:
    with open('$CONFIG_FILE', 'r') as f:
        config = yaml.safe_load(f)
    
    # Get default host from settings
    default_host = '127.0.0.1'
    if 'settings' in config and 'synth_host' in config['settings']:
        default_host = config['settings']['synth_host']
    
    # Print each voice's host and port
    for voice in config.get('voices', []):
        host = voice.get('host', default_host)
        port = voice.get('port')
        print(f'{host} {port}')
except Exception as e:
    print(f'Error: {e}', file=sys.stderr)
    exit(1)
")

if [ $? -ne 0 ]; then
  echo "Error processing $CONFIG_FILE"
  exit 1
fi

# Launch Faust instances for local hosts and check remote hosts
LOCAL_SYNTH_PIDS=()

echo "$HOSTS_AND_PORTS" | while read -r host port; do
  if [ -z "$host" ] || [ -z "$port" ]; then
    continue
  fi
  
  if is_local_host "$host"; then
    echo "Starting local Faust instance on $host:$port..."
    $FAUST_BINARY -port "$port" &
    pid=$!
    LOCAL_SYNTH_PIDS+=($pid)
    echo "Started local synth with PID $pid listening on port $port"
    sleep 1 # Give time for synth to initialize
  else
    # For remote hosts, check connectivity
    check_remote_host "$host" "$port"
  fi
done

echo ""
echo "Starting OSC Router on port $ROUTER_PORT..."
python3 osc_router.py -c "$CONFIG_FILE" -p "$ROUTER_PORT" &
ROUTER_PID=$!
sleep 2 # Give router time to initialize

# Handle shutdown gracefully (when user presses Ctrl+C)
function cleanup {
  echo ""
  echo "Shutting down..."
  kill $ROUTER_PID 2>/dev/null
  
  # Kill local synth instances
  for pid in "${LOCAL_SYNTH_PIDS[@]}"; do
    echo "Terminating local synth PID $pid"
    kill $pid 2>/dev/null
  done
  
  echo "All local processes terminated."
  exit 0
}

trap cleanup INT TERM

python3 ui.py &
# Start MIDI-OSC Bridge in foreground
echo "Starting MIDI-OSC Bridge..."
echo "NOTE: Select your MIDI input device when prompted"
echo ""
python3 midi_osc.py

# If the MIDI-OSC bridge exits, clean up other processes
cleanup 
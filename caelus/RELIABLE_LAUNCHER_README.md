# Reliable Caelus Launcher

This script provides a more reliable startup sequence for Caelus with a GUI, similar to the headless mode but with full visualization.

## Why Use This Launcher?

The traditional Caelus launcher can sometimes have issues with the startup sequence:

- Router and synths might not start in the optimal order
- Synth connections may not be verified
- Cleanup on exit might be incomplete

This reliable launcher addresses these issues by:

1. Checking for and killing existing processes
2. Starting the OSC router first
3. Loading synths from voices.yaml
4. Verifying synth connections
5. Launching the GUI with proper flags
6. Providing comprehensive cleanup on exit

## Usage

### Basic Usage

```bash
./reliable_launcher.py
```

This will start Caelus with the default preset ("00 - Simple Mono") and ports.

### Custom Preset and Ports

```bash
./reliable_launcher.py "01 - PolySynth" 9000 9001
```

Where:
- `01 - PolySynth` is the preset name
- `9000` is the router port
- `9001` is the UI port

## Command-line Arguments

- `[preset_name]`: The name of the preset to use (default: "00 - Simple Mono")
- `[router_port]`: The port for the OSC router (default: 9000)
- `[ui_port]`: The port for UI feedback (default: 9001)

## Startup Sequence

1. Kill any existing Caelus processes
2. Load preset configuration
3. Start OSC router in background
4. Launch synth processes
5. Verify synth connections
6. Launch GUI with the `--no-auto-start-router` flag

## Cleanup

The launcher performs thorough cleanup:
- When you press Ctrl+C
- When the GUI process exits
- In case of unexpected errors

## Troubleshooting

If the launcher fails to start:

1. Check if any of the ports are already in use
2. Verify that the preset exists in the "presets" directory
3. Check that the synth binary path in the preset's voices.yaml file is correct
4. Examine the log output for specific errors

## Note on Process Management

This launcher takes an aggressive approach to process management to prevent orphaned processes. It will:

1. Track all processes it spawns
2. Search for any remaining synth processes during cleanup
3. Send SIGTERM first, followed by SIGKILL if necessary

## Making Executable

Run this command to make the launcher executable:

```bash
chmod +x reliable_launcher.py
``` 
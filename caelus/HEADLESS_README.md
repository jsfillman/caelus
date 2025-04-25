# Caelus Headless Mode

This directory contains scripts for running Caelus in a headless mode, without the GUI. These scripts are useful for testing and development.

## Scripts

1. **headless_router.py** - Starts the OSC router with the specified preset
2. **play_notes.py** - Sends specific note patterns to the router
3. **continuous_play.py** - Continuously sends random notes or chord progressions to the router

## Basic Workflow

1. Start the headless router
2. Start playing notes with one of the player scripts

## Usage Examples

### Step 1: Start the Headless Router

```bash
# Start with default preset (00 - Simple Mono)
./headless_router.py

# Specify a different preset
./headless_router.py "01 - Simple Poly"

# Specify a different router port
./headless_router.py "00 - Simple Mono" 9010
```

### Step 2: Play Notes

**Play a scale:**
```bash
./play_notes.py --mode scale
```

**Play a melody:**
```bash
./play_notes.py --mode melody
```

**Play a chord:**
```bash
./play_notes.py --mode chord --chord maj7
```

**Play a single note:**
```bash
./play_notes.py --mode single --note 60 --duration 1.0
```

### Continuous Play

**Play random notes:**
```bash
./continuous_play.py --mode random --duration 0.3 --interval 0.2 --count 30
```

**Play chord progression:**
```bash
./continuous_play.py --mode chords --root 48 --duration 1.0 --interval 0.2 --cycles 2
```

## Options

### headless_router.py

```
positional arguments:
  preset_name           Preset to load (default: "00 - Simple Mono")
  router_port           OSC router port (default: 9000)
```

### play_notes.py

```
--port PORT             Router port (default: 9000)
--ip IP                 Router IP (default: 127.0.0.1)
--router ROUTER         Router name (default: router)
--mode {scale,melody,chord,single}
                        What to play (default: scale)
--note NOTE             Starting note (MIDI number, default: 60 = C4)
--velocity VELOCITY     Note velocity (0.0-1.0, default: 0.8)
--duration DURATION     Note duration in seconds (default: 0.5)
--chord {major,minor,7th,maj7,min7}
                        Chord type for chord mode (default: major)
```

### continuous_play.py

```
--port PORT             Router port (default: 9000)
--ip IP                 Router IP (default: 127.0.0.1)
--router ROUTER         Router name (default: router)
--mode {random,chords}  Play mode (default: random)
--min-note MIN_NOTE     Minimum MIDI note number (default: 48)
--max-note MAX_NOTE     Maximum MIDI note number (default: 84)
--root ROOT             Root note for chord progression (default: 60)
--duration DURATION     Note/chord duration in seconds (default: 0.5)
--interval INTERVAL     Time between new notes/chords (default: 0.25)
--count COUNT           Number of notes to play, 0 for infinite (default: 100)
--cycles CYCLES         Number of chord progression cycles (default: 4)
```

## Debugging

If the router is running but you don't hear any sound, check:

1. That the synth binary is correctly specified in the preset's voices.yaml file
2. That the synth is listening on the specified ports
3. That the router and note player are using the same port (default: 9000)

To see if OSC messages are being sent to the router, you can run the note player with verbose output:

```bash
./play_notes.py --mode single --note 60
```

To stop any of the scripts, press Ctrl+C. This will send an "all notes off" message to the router. 
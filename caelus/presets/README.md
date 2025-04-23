# Caelus Preset System

## Architecture Overview

The preset system allows managing and switching between:
1. Synth **Banks** (different synth engines)
2. **Patches** (parameter presets within a synth bank)

## Directory Structure

```
presets/
├── README.md (this file)
├── simple/ (example synth bank)
│   ├── synth (compiled Faust binary or Pyo script)
│   ├── synth.dsp.json (synth parameter definitions)
│   ├── ui.py (custom UI for this synth)
│   ├── voices.yaml (voice allocation config)
│   └── patches/
│       ├── 00-Default.yaml (default patch)
│       └── ... (other patches)
└── ... (other synth banks)
```

## Implementation Plan

### 1. MIDI-OSC Bridge Enhancements

- Add Bank selection dropdown to replace the button
- Implement Bank loading:
  - Load synth binary/script from bank directory
  - Launch synth instances as defined in bank's voices.yaml
  - Start UI with parameters from default patch
- Implement Patch management:
  - Load Patch: Load parameters from selected YAML file
  - Save Patch: Save current parameters to YAML file
  - Load Bank: Switch to a different synth bank

### 2. Startup Flow

1. `midi_osc.py` launches first
2. User selects a synth bank from dropdown
3. System:
   - Kills any running synth instances
   - Loads appropriate synth binary/script from bank directory
   - Launches synth instances based on bank's voices.yaml
   - Starts UI with parameters from bank's 00-Default.yaml
4. User can then change patches or banks via UI

### 3. Parameter Persistence

- Patches store all synth parameters in YAML format
- Default values come from synth.dsp.json
- UI parameters must be mapped to OSC endpoints

## Implementation Notes

1. Need to modify launch_poly_synth.sh to let midi_osc.py launch everything
2. Ensure clean shutdown of all processes when switching banks
3. Account for different parameter sets between synth types
4. Handle non-existent banks/patches gracefully 
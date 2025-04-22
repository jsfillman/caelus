# Caelus Presets

This directory contains preset files for the Caelus synthesizer in YAML format. These presets define various sound configurations that can be loaded into the Caelus engine.

## Organization

- **Root directory**: Contains general purpose presets and specialized effect presets
  - `default_feedback_delay.yaml`: Default preset with feedback and delay settings
  - `default_pan_lfo.yaml`: Default preset with pan and LFO modulation
  - `evolve.yaml`: Preset with parameters that evolve over time
  - `spacechamber.yaml`: Preset with spatial and reverb/chamber-like qualities

- **patch/**: Contains more specialized sound patches
  - Various instrument and effect emulations (see the patch directory README)

## Usage

To load a preset in Caelus:

```python
# Example usage in code
preset_path = "presets/default_pan_lfo.yaml"
synth.load_preset(preset_path)
```

Or use the GUI preset loader to select and load presets interactively.
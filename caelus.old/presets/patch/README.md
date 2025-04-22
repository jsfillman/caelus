# Caelus Sound Patches

This directory contains specialized sound patches for the Caelus synthesizer. Each YAML file defines a unique sound character that can be loaded as a preset.

## Available Patches

- **clangy.yaml**: Metallic, resonant sounds with clanging qualities
- **default.yaml**: Standard balanced FM sound with moderate settings
- **epiano.yaml**: Electric piano emulation with characteristic bell-like attack
- **extreme-mod.yaml**: Extreme modulation settings for experimental sounds
- **sine.yaml**: Pure sine wave based sounds with minimal harmonics
- **skrillbass.yaml**: Aggressive bass sound inspired by dubstep/EDM
- **skrillbass2.yaml**: Variation on the skrillbass with different character

## Usage

These patches can be loaded from the preset browser in the Caelus interface, or programmatically:

```python
# Example usage
preset_path = "presets/patch/epiano.yaml"
synth.load_preset(preset_path)
```
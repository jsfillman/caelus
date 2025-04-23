## Caelus Refactor



### Launcher 

This will replace the `launch_poly_synth.sh` and top level python scripts with a single `caelus` entrypoint.

- Move current `midi_osc.py` and `osc_router.py` to their respective directories under `lib/`
  - Update import paths for same directory imports vs lib/x/module.py
- Create a new `caelus` script to launch all services:
  - Move UI code from midi_osc to launcher
  - Use `CaelusAppIcon.png` to create a macOS launcher icon (vs default Python rocket image)
- Ensure functionality remains the same as previously:
  - Select midi interface (via midi_osc.py libs)
  - Select bank (directories under presets)
  - Select patch (yaml files under presets/preset/patches)
  - Load X number of `synth` instances, based on bank's voices.yaml
  - Load bank's UI via its `ui.py`
- Improve startup:
  - Add splash image based on `Caelus.png`
  - Automatically select first interface (current default behavior I believe?)
  - Automatically load default patch `00 - Simple Mono`
- Improve UI:
  - Move synth loading info into the UI
  - Show a status bar of X of Y synths loaded (eg. 16 of 16)
  - Periodically rescan synths for connectivity (may require some new logic)

### Synth UI

- Make the default screen size 2224 × 1668, to match an iPad in landscape mode
- Allow custom icons for the synth UI window via AppIcon.png in the preset dir
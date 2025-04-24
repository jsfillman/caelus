# Claude.md - Caelus Refactoring Guide

This document outlines the refactoring needed for the Caelus synthesizer system, based on the requirements in CaelusRefactor.md.

## 1. Create a unified launcher script

Create a new `caelus` script that:

- Replaces `launch_poly_synth.sh`, `midi_osc.py` and acts as the single entry point
- Shows a splash screen using `Caelus.png`
- Auto-selects the first MIDI interface
- Auto-loads the default bank ("00 - Simple Mono")
  - Add synth loading progress indicator showing "X of Y synths connected"
  - Add periodic connectivity checks for synths

## 2. Move Python modules to appropriate directories

- Move `midi_osc.py` to `lib/midi_osc/main.py`
- Move `osc_router.py` to `lib/osc_bridge/main.py`
- Update import paths for all modules

## 3. Enhance Synth UI functionality

- Use standard iPad dimensions (2224 × 1668) for optimal display
- Support custom window icons via `AppIcon.png` in preset directories
- Add proper status bar for system information

## 4. Implementation details

- Use `PyQt6.QtWidgets.QSplashScreen` for the splash screen
- Add a connectivity monitor that pings voices every 30 seconds
- Support the existing functionality while improving the user experience
- Use color coding for connectivity status (green: all connected, orange: partial, red: none)

The existing code structure is sound - this refactoring focuses on improving the launcher experience and UI without changing the core functionality.
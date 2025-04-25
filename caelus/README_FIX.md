# Caelus OSC Router Voice Fix

This document explains the emergency fix that was implemented for the Caelus synthesizer system to address a critical issue where the OSC router was initializing with 0 voices, resulting in no sound output.

## The Problem

The Caelus system has the following communication flow:
1. MIDI input is received by the MIDI-OSC bridge
2. The MIDI-OSC bridge converts MIDI to OSC messages and sends them to the router
3. The router allocates voices and forwards OSC messages to the synth
4. The synth produces sound

The critical issue was that the router was initializing with 0 voices, even though the configuration file (`voices.yaml`) was valid. Without voices, the router couldn't forward any messages to the synth, resulting in no sound output.

## Diagnostic Steps Taken

1. Verified that MIDI-OSC bridge was receiving MIDI input and sending OSC messages to the router
2. Confirmed that the router was receiving these messages but had 0 voices to handle them
3. Tested direct OSC communication with the synth, which worked correctly
4. Attempted to add emergency voices to the running router, which didn't work
5. Created a monkey patch to ensure the router always has at least one voice

## The Fix

The fix consists of a Python script (`router_emergency_patch.py`) that monkey patches the OSC router to ensure it always has at least one voice. The patch:

1. Overrides the `__init__` method of `OSCRouter` to add an emergency voice if none are loaded from the config
2. Overrides the `__init__` method of `VoiceManager` to ensure it never initializes with an empty voices list
3. Adds debug logging to the `handle_note_on` method to verify that voices are available when notes are played

## How to Use

The fix is automatically applied when you run the `caelus` script. If you're using a different entry point, you should add the following import before creating any OSC components:

```python
import router_emergency_patch
```

## Long-Term Solution

This is a temporary fix to get the system working. For a proper long-term solution, you should:

1. Investigate why the router is initializing with 0 voices despite the config file being valid
2. Ensure that the voice loading code is robust and correctly handles all edge cases
3. Add proper error handling and fallback mechanisms for voice allocation

## Testing

To verify that the fix is working:

1. Run Caelus normally
2. Check the console output for messages like:
   ```
   !!! Router initialized with 0 voices from config !!!
   !!! EMERGENCY FIX: No voices found, adding emergency voice !!!
   !!! Added emergency voice: Voice(id=emergency_voice, port=5910, host=127.0.0.1, note=None, active=False) !!!
   ```
3. Play a MIDI note and check for messages like:
   ```
   !!! NOTE ON: 60 velocity=0.8 !!!
   !!! Router has 1 voices available !!!
   ```
4. Confirm that sound is produced when playing MIDI notes

## Troubleshooting

If you're still not getting sound:

1. Run `./direct_voice_test.py` to verify that direct OSC communication with the synth works
2. Check that the synth process is running (`ps aux | grep synth`)
3. Verify that the synth is listening on port 5910 (`lsof -i :5910`)
4. Check the error logs for any issues with the synth process

## Contact

If you have any questions or issues with this fix, please contact the Caelus development team.
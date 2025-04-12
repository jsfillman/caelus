#!/usr/bin/env python3
"""
Caelux Mini Launcher
This script provides options to launch either the main application
or the audio setup utility.
"""

import os
import sys
import argparse
import subprocess

def main():
    parser = argparse.ArgumentParser(description="Caelux Mini Launcher")
    parser.add_argument('--setup', action='store_true', 
                        help='Launch the audio setup utility instead of the main application')
    parser.add_argument('--reset-audio', action='store_true',
                        help='Reset audio settings to default before launching')
    args = parser.parse_args()
    
    # Get script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Check if we need to reset audio settings
    if args.reset_audio:
        audio_settings_file = os.path.join(script_dir, "audio_settings.yaml")
        if os.path.exists(audio_settings_file):
            try:
                os.remove(audio_settings_file)
                print(f"Removed audio settings file: {audio_settings_file}")
            except Exception as e:
                print(f"Error removing audio settings file: {e}")
    
    # Determine which script to run
    if args.setup:
        # Launch the audio setup utility
        script_path = os.path.join(script_dir, "audio_setup.py")
    else:
        # Launch the main application
        script_path = os.path.join(script_dir, "main_updated.py")
    
    # Check if script exists
    if not os.path.exists(script_path):
        print(f"Error: Could not find script at {script_path}")
        return 1
    
    # Launch the script
    print(f"Launching: {script_path}")
    try:
        subprocess.run([sys.executable, script_path])
        return 0
    except Exception as e:
        print(f"Error launching script: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
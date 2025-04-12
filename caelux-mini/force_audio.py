#!/usr/bin/env python3
"""
Force Caelux Mini to use a specific audio device (Loopback Audio 2)
"""

import os
import sys
import yaml

def main():
    # Hardcoded settings for Loopback Audio 2
    settings = {
        'device_index': 5,  # Force index 5 (Loopback Audio 2)
        'device_name': 'Loopback Audio 2',
        'sample_rate': 44100,
        'buffer_size': 256,
        'num_channels': 4  # Use quad output
    }
    
    # Create audio settings file with absolute path
    audio_settings_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio_settings.yaml")
    
    try:
        # Save the settings
        with open(audio_settings_file, 'w') as f:
            yaml.dump(settings, f)
            
        print(f"Forced audio settings saved to {audio_settings_file}")
        print(f"Device Index: {settings['device_index']} ({settings['device_name']})")
        print(f"Sample Rate: {settings['sample_rate']} Hz")
        print(f"Buffer Size: {settings['buffer_size']}")
        print(f"Channels: {settings['num_channels']}")
        
        # Launch the main app
        main_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main_updated.py")
        if os.path.exists(main_script):
            print(f"\nLaunching Caelux Mini...")
            import subprocess
            subprocess.Popen([sys.executable, main_script])
            return 0
        else:
            print(f"Error: Could not find main script at {main_script}")
            return 1
            
    except Exception as e:
        print(f"Error setting forced audio device: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
#!/usr/bin/env python3
"""
Simple 4-channel audio test script
Plays test tones to all 4 channels on the default audio device
"""

import pyo
import time
import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description='Test quad audio output')
    parser.add_argument('--device', type=int, help='Audio device index to use', default=None)
    parser.add_argument('--channels', type=int, help='Number of channels to test', default=4)
    parser.add_argument('--list', action='store_true', help='List available devices')
    args = parser.parse_args()
    
    # List devices if requested
    if args.list:
        print("AVAILABLE AUDIO DEVICES")
        print("======================")
        try:
            devices = pyo.pa_get_output_devices()
            print(f"Device format: {type(devices)}")
            
            if isinstance(devices, dict):
                for idx, name in sorted(devices.items()):
                    print(f"Device {idx}: {name}")
            elif isinstance(devices, tuple) and len(devices) == 2:
                names = devices[0]
                indices = devices[1]
                for i, name in enumerate(names):
                    idx = indices[i] if i < len(indices) else i
                    print(f"Device {idx}: {name}")
            else:
                print(f"Unknown device format: {devices}")
        except Exception as e:
            print(f"Error listing devices: {e}")
        return 0
    
    # Print info
    print("QUAD CHANNEL AUDIO TEST")
    print("======================")
    print(f"Testing with {args.channels} channels")
    if args.device is not None:
        print(f"Forcing device index: {args.device}")
    else:
        print("Using default device")
    
    # Create the server
    try:
        # Note: duplex=0 to disable input
        s = pyo.Server(nchnls=args.channels, duplex=0)
        s.boot()
        print("Server booted")
        
        # Set device if specified
        if args.device is not None:
            print(f"Setting output device to {args.device}")
            try:
                s.setOutputDevice(args.device)
                print(f"Output device set")
            except Exception as e:
                print(f"Error setting output device: {e}")
        
        # Get info
        device = None
        try:
            device = s.getOutputDevice()
            print(f"Active device index: {device}")
        except Exception as e:
            print(f"Could not get output device: {e}")
            print("Using default device")
        
        # Get device name if possible
        device_name = "Unknown"
        try:
            devices = pyo.pa_get_output_devices()
            if isinstance(devices, dict) and device is not None:
                device_name = devices.get(device, "Unknown")
            elif isinstance(devices, tuple) and len(devices) == 2 and device is not None:
                names = devices[0]
                indices = devices[1]
                if device in indices:
                    idx = indices.index(device)
                    if idx < len(names):
                        device_name = names[idx]
            print(f"Device name: {device_name}")
        except Exception as e:
            print(f"Could not get device name: {e}")
        
        # Get channel count
        try:
            channels = s.getNchnls()
            print(f"Active channels: {channels}")
        except Exception as e:
            print(f"Could not get channel count: {e}")
            channels = args.channels
        
        # Start the server
        s.start()
        print("Server started")
        
        # Play test tones on each channel
        print("\nPlaying test tones on each channel...")
        
        for ch in range(channels):
            # Different frequency for each channel
            freq = 440 * (1 + ch * 0.25)  # A4, C#5, F#5, B5
            
            # Display info
            channel_names = ["Front Left", "Front Right", "Rear Left", "Rear Right"]
            channel_name = channel_names[ch] if ch < len(channel_names) else f"Channel {ch}"
            print(f"Playing on {channel_name} (channel {ch}) at {freq} Hz...")
            
            # Create tone
            sine = pyo.Sine(freq=freq, mul=0.3)
            
            # Route to specific channel
            out = pyo.Mix(sine, voices=1)
            out.out(chnl=ch)
            
            # Let it play briefly
            time.sleep(1.0)
            
            # Clean up
            sine.stop()
            out.stop()
            
            # Pause between tones
            time.sleep(0.5)
        
        print("\nTest complete!")
        
        # Ask user to confirm if they heard all channels
        heard_all = input("Did you hear all channels? (y/n): ")
        if heard_all.lower().startswith('y'):
            print("Great! Quad audio is working.")
        else:
            print("Some channels were not heard.")
            
        # Clean up
        s.stop()
        print("Server stopped")
        s.shutdown()
        print("Server shutdown")
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
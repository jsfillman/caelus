#!/usr/bin/env python3
"""
Check all audio devices recognized by Pyo
"""

import pyo
import sys
import time

def main():
    print("PYO AUDIO DEVICE CHECKER")
    print("=" * 50)
    
    # Try to get device info using all methods
    try:
        print("\nMethod 1: pa_get_output_devices()")
        devices = pyo.pa_get_output_devices()
        print(f"Type: {type(devices)}")
        print(f"Data: {devices}")
        
        # Try to interpret the structure
        if isinstance(devices, dict):
            for idx, name in sorted(devices.items()):
                print(f"  Device {idx}: {name}")
        elif isinstance(devices, (list, tuple)) and len(devices) == 2:
            # Special ([names], [indices]) format
            names = devices[0]
            indices = devices[1]
            for i in range(len(names)):
                if i < len(indices):
                    print(f"  Device {indices[i]}: {names[i]}")
        elif isinstance(devices, (list, tuple)):
            # Standard list
            for i, name in enumerate(devices):
                print(f"  Device {i}: {name}")
    except Exception as e:
        print(f"Error with Method 1: {e}")
    
    try:
        print("\nMethod 2: pa_get_devices_infos()")
        devices_info = pyo.pa_get_devices_infos()
        print(f"Type: {type(devices_info)}")
        print(f"Count: {len(devices_info)}")
        
        for i, dev in enumerate(devices_info):
            print(f"\nDevice {i}:")
            if isinstance(dev, dict):
                for key, value in dev.items():
                    print(f"  {key}: {value}")
    except Exception as e:
        print(f"Error with Method 2: {e}")
    
    # Try creating and checking servers
    try:
        print("\nTesting audio servers:")
        
        # First without specifying device
        print("\nServer 1: Default device")
        s1 = pyo.Server(nchnls=2)
        s1.boot()
        print(f"Using device: {s1.getOutputDevice()}")
        try:
            device_name = pyo.pa_get_output_devices()[s1.getOutputDevice()]
            print(f"Device name: {device_name}")
        except:
            print("Could not get device name")
        print(f"Channels: {s1.getNchnls()}")
        s1.start()
        print("Started: Yes")
        s1.stop()
        
        # Now try for each possible device index
        test_indices = list(range(10))  # Try devices 0-9
        
        for idx in test_indices:
            try:
                print(f"\nServer: Testing device {idx}")
                s = pyo.Server(nchnls=4)
                s.boot()
                print(f"  Default device: {s.getOutputDevice()}")
                try:
                    s.setOutputDevice(idx)
                    print(f"  Set device to: {idx}")
                    print(f"  Active device: {s.getOutputDevice()}")
                    s.start()
                    
                    # Create a test sound to see if it works
                    a = pyo.Sine(freq=440, mul=0.1).out()
                    print("  Playing test tone...")
                    time.sleep(0.5)
                    a.stop()
                    
                    # Test quad routing
                    print("  Testing quad routing...")
                    tones = []
                    for ch in range(min(4, s.getNchnls())):
                        # Create a tone for each channel with different frequencies
                        freq = 440 * (1 + ch * 0.25)
                        print(f"    Channel {ch}: {freq} Hz")
                        tone = pyo.Sine(freq=freq, mul=0.1)
                        mixer = pyo.Mixer(voices=1, chnls=s.getNchnls())
                        mixer.addInput(0, tone)
                        mixer.setAmp(0, ch, 1.0)
                        mixer.out()
                        tones.append((tone, mixer))
                        time.sleep(0.5)
                    
                    # Clean up
                    for tone, mixer in tones:
                        tone.stop()
                        mixer.stop()
                    
                    print(f"  Channels: {s.getNchnls()}")
                    print("  Started: Yes")
                    s.stop()
                    print("  Success!")
                except Exception as e:
                    print(f"  Error testing device {idx}: {e}")
            except Exception as e:
                print(f"  Could not test device {idx}: {e}")
    
    except Exception as e:
        print(f"Error testing servers: {e}")
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
#!/usr/bin/env python3
"""
Direct Loopback Audio 2 test with no other pyo instances running
The goal is to find a sequence that reliably uses Loopback Audio 2
"""

import pyo
import sys
import time
import os

def main():
    print("\nLOOPBACK AUDIO 2 DIRECT TEST")
    print("============================")
    
    # Let's try different sequences of server creation and device selection
    
    # Step 0: Define the device we want
    LOOPBACK_DEVICE = 5  # Loopback Audio 2
    CHANNELS = 8
    
    # Step 1: Try to pre-set the default output device using pyo.pm_set_default_output()
    try:
        print("\nMethod 1: Using pm_set_default_output")
        print(f"Setting default output to device {LOOPBACK_DEVICE}")
        pyo.pm_set_default_output(LOOPBACK_DEVICE)
        print("Default output device set")
        
        # Now create the server
        s1 = pyo.Server(nchnls=CHANNELS, duplex=0)
        s1.boot()
        
        # Check what device was selected
        try:
            device = s1.getOutputDevice()
            print(f"Selected device: {device}")
            channels = s1.getNchnls()
            print(f"Channels: {channels}")
            
            # Test it
            if device == LOOPBACK_DEVICE:
                print("SUCCESS! Loopback Audio 2 selected")
                s1.start()
                
                # Play test tone
                print("Playing test tone...")
                a = pyo.Sine(freq=440, mul=0.3).out()
                time.sleep(1.0)
                a.stop()
                
                s1.stop()
                print("Method 1 works!")
            else:
                print("Failed to select Loopback Audio 2")
                s1.shutdown()
        except Exception as e:
            print(f"Error checking device: {e}")
            s1.shutdown()
    except Exception as e:
        print(f"Method 1 failed: {e}")
    
    # Step 2: Try setting PA_RECOMMENDED_OUTPUT_DEVICE environment variable
    try:
        print("\nMethod 2: Using environment variable")
        os.environ["PA_RECOMMENDED_OUTPUT_DEVICE"] = str(LOOPBACK_DEVICE)
        print(f"Set PA_RECOMMENDED_OUTPUT_DEVICE={LOOPBACK_DEVICE}")
        
        # Now create the server
        s2 = pyo.Server(nchnls=CHANNELS, duplex=0)
        s2.boot()
        
        # Check what device was selected
        try:
            device = s2.getOutputDevice()
            print(f"Selected device: {device}")
            channels = s2.getNchnls()
            print(f"Channels: {channels}")
            
            # Test it
            if device == LOOPBACK_DEVICE:
                print("SUCCESS! Loopback Audio 2 selected")
                s2.start()
                
                # Play test tone
                print("Playing test tone...")
                a = pyo.Sine(freq=440, mul=0.3).out()
                time.sleep(1.0)
                a.stop()
                
                s2.stop()
                print("Method 2 works!")
            else:
                print("Failed to select Loopback Audio 2")
                s2.shutdown()
        except Exception as e:
            print(f"Error checking device: {e}")
            s2.shutdown()
    except Exception as e:
        print(f"Method 2 failed: {e}")
    
    # Step 3: Try predefining the device in the server constructor
    try:
        print("\nMethod 3: Using device in server constructor")
        
        # Now create the server with the device parameter
        s3 = pyo.Server(nchnls=CHANNELS, duplex=0, audio="pa", device=LOOPBACK_DEVICE)
        print(f"Created server with device={LOOPBACK_DEVICE}")
        s3.boot()
        
        # Check what device was selected
        try:
            device = s3.getOutputDevice()
            print(f"Selected device: {device}")
            channels = s3.getNchnls()
            print(f"Channels: {channels}")
            
            # Test it
            if device == LOOPBACK_DEVICE:
                print("SUCCESS! Loopback Audio 2 selected")
                s3.start()
                
                # Play test tone
                print("Playing test tone...")
                a = pyo.Sine(freq=440, mul=0.3).out()
                time.sleep(1.0)
                a.stop()
                
                s3.stop()
                print("Method 3 works!")
            else:
                print("Failed to select Loopback Audio 2")
                s3.shutdown()
        except Exception as e:
            print(f"Error checking device: {e}")
            s3.shutdown()
    except Exception as e:
        print(f"Method 3 failed: {e}")
    
    # Step 4: Try using the "audio" parameter differently
    try:
        print("\nMethod 4: Using specific audio backend configuration")
        
        # Create parameter string for portaudio
        # Format: pa_out_X where X is the device number
        audio_backend = f"pa_out_{LOOPBACK_DEVICE}"
        print(f"Audio backend string: {audio_backend}")
        
        # Create the server with this configuration
        s4 = pyo.Server(nchnls=CHANNELS, duplex=0, audio=audio_backend)
        print(f"Created server with audio={audio_backend}")
        s4.boot()
        
        # Check what device was selected
        try:
            device = s4.getOutputDevice()
            print(f"Selected device: {device}")
            channels = s4.getNchnls()
            print(f"Channels: {channels}")
            
            # Test it
            if device == LOOPBACK_DEVICE:
                print("SUCCESS! Loopback Audio 2 selected")
                s4.start()
                
                # Play test tone
                print("Playing test tone...")
                a = pyo.Sine(freq=440, mul=0.3).out()
                time.sleep(1.0)
                a.stop()
                
                s4.stop()
                print("Method 4 works!")
            else:
                print("Failed to select Loopback Audio 2")
                s4.shutdown()
        except Exception as e:
            print(f"Error checking device: {e}")
            s4.shutdown()
    except Exception as e:
        print(f"Method 4 failed: {e}")
        
    # Step 5: Try a completely different approach with a preference file
    try:
        print("\nMethod 5: Using preference file")
        
        # Create a preference file
        pref_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".pyo_prefs")
        with open(pref_file, "w") as f:
            f.write(f"OUTPUT_DEVICE = {LOOPBACK_DEVICE}\n")
            f.write(f"NCHNLS = {CHANNELS}\n")
        
        print(f"Created preference file at {pref_file}")
        
        # Now create a server and see if it reads the preferences
        s5 = pyo.Server(duplex=0)
        print("Created server with no parameters")
        s5.boot()
        
        # Check what device was selected
        try:
            device = s5.getOutputDevice()
            print(f"Selected device: {device}")
            channels = s5.getNchnls()
            print(f"Channels: {channels}")
            
            # Test it
            if device == LOOPBACK_DEVICE:
                print("SUCCESS! Loopback Audio 2 selected")
                s5.start()
                
                # Play test tone
                print("Playing test tone...")
                a = pyo.Sine(freq=440, mul=0.3).out()
                time.sleep(1.0)
                a.stop()
                
                s5.stop()
                print("Method 5 works!")
            else:
                print("Failed to select Loopback Audio 2")
                s5.shutdown()
        except Exception as e:
            print(f"Error checking device: {e}")
            s5.shutdown()
    except Exception as e:
        print(f"Method 5 failed: {e}")
    
    # Summarize results
    print("\nTEST COMPLETE")
    print("=============")
    print("If any method worked, we can use that approach for the main application.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
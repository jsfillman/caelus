"""
Simple utility to display audio device information from pyo
"""

import pyo
import sys

def main():
    print("Pyo Audio Device Debugger")
    print("-" * 50)
    
    try:
        # Get list of audio devices
        print("Getting audio device information...")
        audio_info = pyo.pa_get_devices_infos()
        
        # Print all device info
        print("\nAudio Device List:")
        print("-" * 50)
        
        for i, dev in enumerate(audio_info):
            # Basic device info
            dev_name = dev.get('name', 'Unknown Device')
            host_api = dev.get('host api name', 'Unknown API')
            in_channels = dev.get('maxInputs', 0)
            out_channels = dev.get('maxOutputs', 0)
            default_in = dev.get('defaultIn', False)
            default_out = dev.get('defaultOut', False)
            
            # Print device summary
            print(f"Device {i}: {dev_name}")
            print(f"  API: {host_api}")
            print(f"  Input Channels: {in_channels}")
            print(f"  Output Channels: {out_channels}")
            print(f"  Default Input: {default_in}")
            print(f"  Default Output: {default_out}")
            
            # Print detailed device info
            print("  Full Device Info:")
            for key, value in dev.items():
                print(f"    {key}: {value}")
            
            print("-" * 50)
        
        # Try to get default devices
        print("\nDefault Device Information:")
        print("-" * 50)
        
        try:
            # Create a server instance
            server = pyo.Server(duplex=1)
            
            # Try various methods to get default devices
            methods = [
                ("getDefaultInput", "Default Input Device"),
                ("getDefaultOutput", "Default Output Device"),
                ("getDefaultInputDevice", "Default Input Device Index"),
                ("getDefaultOutputDevice", "Default Output Device Index"),
                ("getInputDevices", "Available Input Devices"),
                ("getOutputDevices", "Available Output Devices"),
            ]
            
            for method_name, description in methods:
                try:
                    if hasattr(server, method_name):
                        value = getattr(server, method_name)()
                        print(f"{description}: {value}")
                    else:
                        print(f"{description}: Method '{method_name}' not available")
                except Exception as e:
                    print(f"{description}: Error - {e}")
            
            # Get sampling rate and buffer size
            try:
                print(f"Default Sampling Rate: {server.getSamplingRate()}")
                print(f"Default Buffer Size: {server.getBufferSize()}")
            except Exception as e:
                print(f"Error getting sampling rate/buffer size: {e}")
            
        except Exception as e:
            print(f"Error creating server: {e}")
        
        print("\nTrying to boot server...")
        try:
            # Try to boot and get active settings
            server = pyo.Server()
            server.boot()
            print("Server booted successfully!")
            
            print(f"Active Sampling Rate: {server.getSamplingRate()}")
            print(f"Active Buffer Size: {server.getBufferSize()}")
            
            # Get active device information
            try:
                active_input = server.getInputDevice()
                active_output = server.getOutputDevice()
                print(f"Active Input Device: {active_input}")
                print(f"Active Output Device: {active_output}")
                
                # Try to match with device names
                if 0 <= active_input < len(audio_info):
                    print(f"Active Input Name: {audio_info[active_input].get('name', 'Unknown')}")
                
                if 0 <= active_output < len(audio_info):
                    print(f"Active Output Name: {audio_info[active_output].get('name', 'Unknown')}")
            except Exception as e:
                print(f"Error getting active devices: {e}")
            
            # Clean up
            server.shutdown()
            
        except Exception as e:
            print(f"Error booting server: {e}")
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

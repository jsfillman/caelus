#!/usr/bin/env python3

import time
from pythonosc import udp_client

def main():
    # Create OSC client
    client = udp_client.SimpleUDPClient("127.0.0.1", 5510)
    synth_name = "legato_synth_stereo"
    
    # Initialize synth with basic parameters
    print("Initializing synth...")
    client.send_message(f"/{synth_name}/wave_type", 2)  # sawtooth
    client.send_message(f"/{synth_name}/gain", 0.7)
    client.send_message(f"/{synth_name}/cutoff_L", 5000)
    client.send_message(f"/{synth_name}/cutoff_R", 5000)
    
    # Test different ramp scenarios
    tests = [
        # (start_freq, end_freq, ramp_time, hold_time)
        (220, 880, 2.0, 0.5),    # 1 octave up over 2 seconds
        (880, 220, 2.0, 0.5),    # 1 octave down over 2 seconds
        (440, 880, 0.5, 0.5),    # Fast up
        (880, 440, 0.5, 0.5),    # Fast down
    ]
    
    for start_freq, end_freq, ramp_time, hold_time in tests:
        print(f"\nTesting ramp from {start_freq}Hz to {end_freq}Hz over {ramp_time}s")
        
        # Set ramp parameters
        client.send_message(f"/{synth_name}/start_freq", start_freq)
        client.send_message(f"/{synth_name}/end_freq", end_freq)
        client.send_message(f"/{synth_name}/ramp_time", ramp_time)
        
        # Start the sound
        client.send_message(f"/{synth_name}/gate", 1.0)
        
        # Wait for ramp and hold
        time.sleep(ramp_time + hold_time)
        
        # Stop the sound
        client.send_message(f"/{synth_name}/gate", 0.0)
        time.sleep(0.5)  # Wait for release

if __name__ == "__main__":
    main() 
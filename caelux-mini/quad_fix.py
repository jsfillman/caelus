#!/usr/bin/env python3
"""
Modified oscillator setup for proper quad routing
Apply this patch to fix channels 2-3 not receiving audio
"""

import os
import sys
import shutil
import re

# Files to modify
OSCILLATOR_FILE = "oscillator.py"
PARTICLE_FILE = "particle.py"

# Create backup files first
def backup_files():
    """Create backups of the files we're going to modify"""
    for file in [OSCILLATOR_FILE, PARTICLE_FILE]:
        backup = file + ".bak"
        if not os.path.exists(backup):
            shutil.copy(file, backup)
            print(f"Created backup: {backup}")

def modify_oscillator():
    """Modify the oscillator.py file to fix multichannel routing"""
    if not os.path.exists(OSCILLATOR_FILE):
        print(f"Error: {OSCILLATOR_FILE} not found.")
        return False
    
    with open(OSCILLATOR_FILE, 'r') as f:
        content = f.read()
    
    # Replace the stereo panner code with direct multichannel output
    # Find the section that creates the stereo panner
    panner_pattern = r"# Default stereo width.*?# Final stereo output\s+self.stereo = self.width_processor"
    
    # New multichannel code to replace it with
    multichannel_code = """
        # Multichannel direct output setup - no stereo panner
        # Create a mono mix of the left and right delay outputs
        self.mono_mix = pyo.Mix([self.left_delay_selector, self.right_delay_selector])
        
        # This is our main output signal that will be routed to channels
        self.stereo = self.mono_mix
        """
    
    # Replace the panner code with our new code (using dotall to match across lines)
    new_content = re.sub(panner_pattern, multichannel_code.strip(), content, flags=re.DOTALL)
    
    # Save the modified file
    with open(OSCILLATOR_FILE, 'w') as f:
        f.write(new_content)
    
    print(f"Modified {OSCILLATOR_FILE} to use direct multichannel output")
    return True

def modify_particle():
    """Modify the particle.py file for better multichannel routing"""
    if not os.path.exists(PARTICLE_FILE):
        print(f"Error: {PARTICLE_FILE} not found.")
        return False
    
    with open(PARTICLE_FILE, 'r') as f:
        content = f.read()
    
    # 1. Update the mixer to use more channels
    mixer_pattern = r"self.mixer = pyo.Mixer\(outs=self.output_channels, chnls=2\)  # 2 channels input, variable output"
    mixer_replacement = "self.mixer = pyo.Mixer(outs=self.output_channels, chnls=1)  # Mono input to multiple outputs"
    
    content = content.replace(mixer_pattern, mixer_replacement)
    
    # 2. Update the channel routing code to use all available channels
    channel_routing_pattern = r"# Multichannel routing based on available channels.*?Audio routing configured with \d+ channels"
    
    # New routing code that uses up to 8 channels
    new_routing = """
        # Enhanced multichannel routing using all available channels
        if car1 and car1.initialized:
            # Connect CAR1 to channels: front left (0) and rear left (2)
            print("Connecting CAR1 to channel 0 (front left)")
            self.set_channel_routing("CAR1", 0, 1.0)
            
            # If we have 4+ channels, use channels 2 (rear left)
            if available_channels >= 4:
                print("Connecting CAR1 to channel 2 (rear left)")
                self.set_channel_routing("CAR1", 2, 1.0)
                
            # If we have 6+ channels, use channels 4 (side left)
            if available_channels >= 6:
                print("Connecting CAR1 to channel 4 (side left)")
                self.set_channel_routing("CAR1", 4, 1.0)
                
            # If we have 8 channels, use channel 6 (back left)
            if available_channels >= 8:
                print("Connecting CAR1 to channel 6 (back left)")
                self.set_channel_routing("CAR1", 6, 1.0)
                
        if car2 and car2.initialized:
            # Connect CAR2 to channels: front right (1) and rear right (3)
            print("Connecting CAR2 to channel 1 (front right)")
            self.set_channel_routing("CAR2", 1, 1.0)
            
            # If we have 4+ channels, use channels 3 (rear right)
            if available_channels >= 4:
                print("Connecting CAR2 to channel 3 (rear right)")
                self.set_channel_routing("CAR2", 3, 1.0)
                
            # If we have 6+ channels, use channels 5 (side right)
            if available_channels >= 6:
                print("Connecting CAR2 to channel 5 (side right)")
                self.set_channel_routing("CAR2", 5, 1.0)
                
            # If we have 8 channels, use channel 7 (back right)
            if available_channels >= 8:
                print("Connecting CAR2 to channel 7 (back right)")
                self.set_channel_routing("CAR2", 7, 1.0)
        
        # Print channel configuration          
        print(f"Audio routing configured with {self.output_channels} channels")
        """
    
    # Replace the routing pattern with our new code (using dotall to match across lines)
    new_content = re.sub(channel_routing_pattern, new_routing.strip(), content, flags=re.DOTALL)
    
    # 3. Update the set_channel_routing method to support more channels
    limit_pattern = r"self.output_channels = min\(4, self.server.getNchnls\(\)\)"
    limit_replacement = "self.output_channels = min(8, self.server.getNchnls())  # Support up to 8 channels"
    
    new_content = new_content.replace(limit_pattern, limit_replacement)
    
    # 4. Fix the mixer input part
    mixer_input_pattern = r"# Connect to mixer with the specified amount.*?self.mixer.setAmp\(channel, 0, amount\)  # Channel, voice, amplitude"
    
    mixer_input_replacement = """
                # Connect to mixer with the specified amount
                if amount > 0:
                    # Use mono input (less likely to have routing issues)
                    mono_signal = pyo.Mix(osc.stereo)
                    self.mixer.addInput(channel, mono_signal)
                    self.mixer.setAmp(channel, 0, amount)  # Channel, voice, amplitude
                """
    
    # Replace the mixer input pattern with our new code (using dotall to match across lines)
    new_content = re.sub(mixer_input_pattern, mixer_input_replacement.strip(), new_content, flags=re.DOTALL)
    
    # Save the modified file
    with open(PARTICLE_FILE, 'w') as f:
        f.write(new_content)
    
    print(f"Modified {PARTICLE_FILE} to use better multichannel routing")
    return True

if __name__ == "__main__":
    print("Fixing quad channel audio routing...")
    backup_files()
    
    if modify_oscillator() and modify_particle():
        print("\nModifications complete! Changes made:")
        print("1. Removed stereo panner in Oscillator class that limited channels to 2")
        print("2. Added direct routing to all available channels (up to 8)")
        print("3. Fixed mixer configuration to use mono input for better multichannel support")
        print("\nRestart the application to apply changes.")
    else:
        print("\nFailed to apply all modifications.")
import yaml
import os
from collections import defaultdict

def save_patch(filename, patch_data):
    """Save a patch dictionary to a YAML file"""
    try:
        with open(filename, 'w') as f:
            yaml.dump(patch_data, f, default_flow_style=False)
        print(f"Patch saved to {filename}")
        return True
    except Exception as e:
        print(f"Error saving patch: {e}")
        return False

def load_patch(filename, gui=None):
    """Load parameters from a YAML file"""
    if not os.path.exists(filename):
        print(f"No patch file found at {filename}")
        return None
    
    try:
        with open(filename, 'r') as f:
            patch_data = yaml.safe_load(f)
        
        if not patch_data:
            print(f"Invalid patch file format: {filename}")
            return None
        
        print(f"Patch loaded from {filename}")
        return patch_data
            
    except Exception as e:
        print(f"Error loading patch: {e}")
        return None
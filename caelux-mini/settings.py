import yaml
import os
from collections import defaultdict

# Custom YAML representer for tuples to use lists instead
def tuple_representer(dumper, data):
    return dumper.represent_list(list(data))

# Add the representer to PyYAML
yaml.add_representer(tuple, tuple_representer)

# Custom list constructor for loading tuples from lists
def tuple_constructor(loader, node):
    # Convert the loaded list back to a tuple
    return tuple(loader.construct_sequence(node))

# Add tuple constructor for safe_load
# This will load lists that were originally tuples back as tuples
# Note: We don't register this by default because it can interfere with regular lists

def save_patch(filename, patch_data):
    """Save a patch dictionary to a YAML file"""
    try:
        # Process any tuples in modulation_matrix to convert them to lists
        if "modulation_matrix" in patch_data:
            processed_matrix = {}
            for source, destinations in patch_data["modulation_matrix"].items():
                # Convert tuples to lists
                processed_matrix[source] = [list(dest) for dest in destinations]
            patch_data["modulation_matrix"] = processed_matrix
        
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
            # Using safe_load without custom constructor to load all as lists
            patch_data = yaml.safe_load(f)
        
        if not patch_data:
            print(f"Invalid patch file format: {filename}")
            return None
        
        # Process modulation_matrix to convert lists back to tuples if needed
        if "modulation_matrix" in patch_data:
            processed_matrix = {}
            for source, destinations in patch_data["modulation_matrix"].items():
                # Convert lists to tuples
                processed_matrix[source] = [tuple(dest) if isinstance(dest, list) else dest 
                                          for dest in destinations]
            patch_data["modulation_matrix"] = processed_matrix
        
        print(f"Patch loaded from {filename}")
        return patch_data
            
    except Exception as e:
        print(f"Error loading patch: {e}")
        return None
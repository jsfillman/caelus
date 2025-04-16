import yaml
import os

def save_patch(filename, voice_manager, vol_control, stability_control):
    """Save all Octolux parameters to a YAML file"""
    
    patch = {}
    
    # Save global parameters
    patch["global"] = {
        "volume": vol_control.value,
        "stability_cents": stability_control.value,
        "max_polyphony": len(voice_manager.voices)
    }
    
    # Save oscillator parameters
    patch["oscillators"] = []
    
    # Get parameters from the first voice's oscillators
    # (since all voices share the same settings)
    voice = voice_manager.voices[0]
    
    for i, osc in enumerate(voice.oscillators):
        osc_data = {
            "id": i,
            "table_name": osc.table_name,
            "semi": osc.semi.get(),
            "cents": osc.cents.get(),
            "attack": osc.attack_val,
            "decay": osc.decay_val,
            "sustain": osc.sustain_val,
            "release": osc.release_val,
            "cutoff": osc.cutoff.get(),
            "lfo_rate": osc.lfo_rate.get(),
            "lfo_depth": osc.lfo_depth.get(),
            "resonance": osc.resonance.get()
        }
        patch["oscillators"].append(osc_data)
    
    try:
        with open(filename, 'w') as f:
            yaml.dump(patch, f, default_flow_style=False)
        print(f"Patch saved to {filename}")
        return True
    except Exception as e:
        print(f"Error saving patch: {e}")
        return False

def load_patch(filename, voice_manager, vol_control, stability_control):
    """Load parameters from a YAML file and apply to Octolux"""
    if not os.path.exists(filename):
        print(f"No patch file found at {filename}")
        return False
    
    try:
        with open(filename, 'r') as f:
            patch = yaml.safe_load(f)
        
        # Load global parameters
        if "global" in patch:
            if "volume" in patch["global"]:
                vol_control.value = patch["global"]["volume"]
            
            if "stability_cents" in patch["global"]:
                stability_control.value = patch["global"]["stability_cents"]
        
        # Load oscillator parameters
        if "oscillators" in patch:
            # For each voice in the voice manager
            for voice in voice_manager.voices:
                # Apply settings to each oscillator
                for osc_data in patch["oscillators"]:
                    # Get oscillator index
                    i = osc_data.get("id", 0)
                    
                    # Make sure we have enough oscillators
                    if i < len(voice.oscillators):
                        osc = voice.oscillators[i]
                        
                        # Apply waveform
                        if "table_name" in osc_data:
                            osc.set_waveform(osc_data["table_name"])
                        
                        # Apply detune
                        if "semi" in osc_data:
                            osc.semi.value = osc_data["semi"]
                        
                        if "cents" in osc_data:
                            osc.cents.value = osc_data["cents"]
                        
                        # Apply ADSR
                        if "attack" in osc_data:
                            osc.set_attack(osc_data["attack"])
                        
                        if "decay" in osc_data:
                            osc.set_decay(osc_data["decay"])
                        
                        if "sustain" in osc_data:
                            osc.set_sustain(osc_data["sustain"])
                        
                        if "release" in osc_data:
                            osc.set_release(osc_data["release"])
                        
                        # Apply filter parameters
                        if "cutoff" in osc_data:
                            osc.cutoff.value = osc_data["cutoff"]
                        
                        if "lfo_rate" in osc_data:
                            osc.lfo_rate.value = osc_data["lfo_rate"]
                        
                        if "lfo_depth" in osc_data:
                            osc.lfo_depth.value = osc_data["lfo_depth"]
                        
                        if "resonance" in osc_data:
                            osc.resonance.value = osc_data["resonance"]
                        
                        # Update detune after changing values
                        osc.update_detune()
        
        print(f"Patch loaded from {filename}")
        return True
    except Exception as e:
        print(f"Error loading patch: {e}")
        return False

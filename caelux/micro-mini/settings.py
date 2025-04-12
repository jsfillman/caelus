import yaml
import os
from collections import defaultdict

def save_patch(filename, gui):
    """Save all GUI parameters to a YAML file"""
    
    patch = defaultdict(dict)
    patch["particle1"]["osc1"] = {
        # Oscillator parameters
        "wave_type": gui.wave_type.currentText(),
        "num_oscs": gui.num_oscs.itemAt(1).widget().value(),
        "detune": gui.detune.itemAt(1).widget().value(),
        "spread": gui.spread.itemAt(1).widget().value(),
        "detune_mode": gui.detune_mode.currentText(),
        "phase_spread": gui.phase_spread.itemAt(1).widget().value(),
        "amp_dist": gui.amp_dist.currentText(),
        
        # Frequency parameters
        "freq_mode": gui.freq_mode.currentText(),
        "manual_freq": gui.manual_freq.itemAt(1).widget().value(),
        "coarse_detune": gui.coarse_detune.itemAt(1).widget().value(),
        "fine_detune": gui.fine_detune.itemAt(1).widget().value(),
        "slew_delay": gui.slew_delay.itemAt(1).widget().value(),
        "slew_time": gui.slew_time.itemAt(1).widget().value(),
        "start_rand": gui.start_rand.itemAt(1).widget().value(),
        "start_slew": gui.start_slew.itemAt(1).widget().value(),
        "end_slew": gui.end_slew.itemAt(1).widget().value(),
        "freq_env_depth": gui.freq_env_depth.itemAt(1).widget().value(),
        "freq_attack": gui.freq_attack.itemAt(1).widget().value(),
        "freq_decay": gui.freq_decay.itemAt(1).widget().value(),
        "freq_sustain": gui.freq_sustain.itemAt(1).widget().value(),
        "freq_release": gui.freq_release.itemAt(1).widget().value(),
        
        # Amplitude parameters
        "amp_ramp_delay": gui.amp_ramp_delay.itemAt(1).widget().value(),
        "amp_ramp_time": gui.amp_ramp_time.itemAt(1).widget().value(),
        "amp_ramp_start": gui.amp_ramp_start.itemAt(1).widget().value(),
        "amp_ramp_end": gui.amp_ramp_end.itemAt(1).widget().value(),
        "amp_attack": gui.amp_attack.itemAt(1).widget().value(),
        "amp_decay": gui.amp_decay.itemAt(1).widget().value(),
        "amp_sustain": gui.amp_sustain.itemAt(1).widget().value(),
        "amp_release": gui.amp_release.itemAt(1).widget().value(),
        
        # Filter parameters
        "filter_res": gui.filter_res.itemAt(1).widget().value(),
        "filter_ramp_delay": gui.filter_ramp_delay.itemAt(1).widget().value(),
        "filter_ramp_time": gui.filter_ramp_time.itemAt(1).widget().value(),
        "filter_ramp_start": gui.filter_ramp_start.itemAt(1).widget().value(),
        "filter_ramp_end": gui.filter_ramp_end.itemAt(1).widget().value(),
        
        # Feedback parameters
        "feedback_source": gui.feedback_source.currentText(),
        "feedback_depth": gui.feedback_depth.itemAt(1).widget().value(),
        
        # Delay parameters
        "left_delay1": gui.left_delays[0].itemAt(1).widget().value(),
        "left_delay2": gui.left_delays[1].itemAt(1).widget().value(),
        "left_delay3": gui.left_delays[2].itemAt(1).widget().value(),
        "right_delay1": gui.right_delays[0].itemAt(1).widget().value(),
        "right_delay2": gui.right_delays[1].itemAt(1).widget().value(),
        "right_delay3": gui.right_delays[2].itemAt(1).widget().value(),
        "left_feedback": gui.left_feedback.itemAt(1).widget().value(),
        "right_feedback": gui.right_feedback.itemAt(1).widget().value(),
    }
    
    # Create dictionary with nested keys for YAML
    patch_data = {"patch": dict(patch)}
    
    try:
        with open(filename, 'w') as f:
            yaml.dump(patch_data, f, default_flow_style=False)
        print(f"Patch saved to {filename}")
        return True
    except Exception as e:
        print(f"Error saving patch: {e}")
        return False

def load_patch(filename, gui):
    """Load parameters from a YAML file and apply to the GUI"""
    if not os.path.exists(filename):
        print(f"No patch file found at {filename}")
        return False
    
    try:
        with open(filename, 'r') as f:
            patch_data = yaml.safe_load(f)
        
        if not patch_data or "patch" not in patch_data:
            print(f"Invalid patch file format: {filename}")
            return False
        
        # Extract the first oscillator settings
        if "particle1" in patch_data["patch"] and "osc1" in patch_data["patch"]["particle1"]:
            settings = patch_data["patch"]["particle1"]["osc1"]
            
            # Apply the settings to the GUI
            
            # Oscillator parameters
            if "wave_type" in settings:
                index = gui.wave_type.findText(settings["wave_type"])
                if index >= 0:
                    gui.wave_type.setCurrentIndex(index)
                    
            if "num_oscs" in settings:
                gui.num_oscs.itemAt(1).widget().setValue(settings["num_oscs"])
                
            if "detune" in settings:
                gui.detune.itemAt(1).widget().setValue(settings["detune"])
                
            if "spread" in settings:
                gui.spread.itemAt(1).widget().setValue(settings["spread"])
                
            if "detune_mode" in settings:
                index = gui.detune_mode.findText(settings["detune_mode"])
                if index >= 0:
                    gui.detune_mode.setCurrentIndex(index)
                    
            if "phase_spread" in settings:
                gui.phase_spread.itemAt(1).widget().setValue(settings["phase_spread"])
                
            if "amp_dist" in settings:
                index = gui.amp_dist.findText(settings["amp_dist"])
                if index >= 0:
                    gui.amp_dist.setCurrentIndex(index)
            
            # Frequency parameters
            if "freq_mode" in settings:
                index = gui.freq_mode.findText(settings["freq_mode"])
                if index >= 0:
                    gui.freq_mode.setCurrentIndex(index)
                    
            if "manual_freq" in settings:
                gui.manual_freq.itemAt(1).widget().setValue(settings["manual_freq"])
                
            if "coarse_detune" in settings:
                gui.coarse_detune.itemAt(1).widget().setValue(settings["coarse_detune"])
                
            if "fine_detune" in settings:
                gui.fine_detune.itemAt(1).widget().setValue(settings["fine_detune"])
                
            if "slew_delay" in settings:
                gui.slew_delay.itemAt(1).widget().setValue(settings["slew_delay"])
                
            if "slew_time" in settings:
                gui.slew_time.itemAt(1).widget().setValue(settings["slew_time"])
                
            if "start_rand" in settings:
                gui.start_rand.itemAt(1).widget().setValue(settings["start_rand"])
                
            if "start_slew" in settings:
                gui.start_slew.itemAt(1).widget().setValue(settings["start_slew"])
                
            if "end_slew" in settings:
                gui.end_slew.itemAt(1).widget().setValue(settings["end_slew"])
                
            if "freq_env_depth" in settings:
                gui.freq_env_depth.itemAt(1).widget().setValue(settings["freq_env_depth"])
                
            if "freq_attack" in settings:
                gui.freq_attack.itemAt(1).widget().setValue(settings["freq_attack"])
                
            if "freq_decay" in settings:
                gui.freq_decay.itemAt(1).widget().setValue(settings["freq_decay"])
                
            if "freq_sustain" in settings:
                gui.freq_sustain.itemAt(1).widget().setValue(settings["freq_sustain"])
                
            if "freq_release" in settings:
                gui.freq_release.itemAt(1).widget().setValue(settings["freq_release"])
            
            # Amplitude parameters
            if "amp_ramp_delay" in settings:
                gui.amp_ramp_delay.itemAt(1).widget().setValue(settings["amp_ramp_delay"])
                
            if "amp_ramp_time" in settings:
                gui.amp_ramp_time.itemAt(1).widget().setValue(settings["amp_ramp_time"])
                
            if "amp_ramp_start" in settings:
                gui.amp_ramp_start.itemAt(1).widget().setValue(settings["amp_ramp_start"])
                
            if "amp_ramp_end" in settings:
                gui.amp_ramp_end.itemAt(1).widget().setValue(settings["amp_ramp_end"])
                
            if "amp_attack" in settings:
                gui.amp_attack.itemAt(1).widget().setValue(settings["amp_attack"])
                
            if "amp_decay" in settings:
                gui.amp_decay.itemAt(1).widget().setValue(settings["amp_decay"])
                
            if "amp_sustain" in settings:
                gui.amp_sustain.itemAt(1).widget().setValue(settings["amp_sustain"])
                
            if "amp_release" in settings:
                gui.amp_release.itemAt(1).widget().setValue(settings["amp_release"])
            
            # Filter parameters
            if "filter_res" in settings:
                gui.filter_res.itemAt(1).widget().setValue(settings["filter_res"])
                
            if "filter_ramp_delay" in settings:
                gui.filter_ramp_delay.itemAt(1).widget().setValue(settings["filter_ramp_delay"])
                
            if "filter_ramp_time" in settings:
                gui.filter_ramp_time.itemAt(1).widget().setValue(settings["filter_ramp_time"])
                
            if "filter_ramp_start" in settings:
                gui.filter_ramp_start.itemAt(1).widget().setValue(settings["filter_ramp_start"])
                
            if "filter_ramp_end" in settings:
                gui.filter_ramp_end.itemAt(1).widget().setValue(settings["filter_ramp_end"])
            
            # Feedback parameters
            if "feedback_source" in settings:
                index = gui.feedback_source.findText(settings["feedback_source"])
                if index >= 0:
                    gui.feedback_source.setCurrentIndex(index)
                    
            if "feedback_depth" in settings:
                gui.feedback_depth.itemAt(1).widget().setValue(settings["feedback_depth"])
            
            # Delay parameters
            if "left_delay1" in settings:
                gui.left_delays[0].itemAt(1).widget().setValue(settings["left_delay1"])
                
            if "left_delay2" in settings:
                gui.left_delays[1].itemAt(1).widget().setValue(settings["left_delay2"])
                
            if "left_delay3" in settings:
                gui.left_delays[2].itemAt(1).widget().setValue(settings["left_delay3"])
                
            if "right_delay1" in settings:
                gui.right_delays[0].itemAt(1).widget().setValue(settings["right_delay1"])
                
            if "right_delay2" in settings:
                gui.right_delays[1].itemAt(1).widget().setValue(settings["right_delay2"])
                
            if "right_delay3" in settings:
                gui.right_delays[2].itemAt(1).widget().setValue(settings["right_delay3"])
                
            if "left_feedback" in settings:
                gui.left_feedback.itemAt(1).widget().setValue(settings["left_feedback"])
                
            if "right_feedback" in settings:
                gui.right_feedback.itemAt(1).widget().setValue(settings["right_feedback"])
            
            print(f"Patch loaded from {filename}")
            return True
        else:
            print("No oscillator settings found in patch file")
            return False
            
    except Exception as e:
        print(f"Error loading patch: {e}")
        return False

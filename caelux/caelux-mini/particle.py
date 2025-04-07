import pyo
from oscillator import Oscillator

class Particle:
    """
    Class to manage a collection of oscillators in a hierarchical structure.
    Oscillators are arranged in a binary tree, with operators modulating carriers.
    """
    
    def __init__(self, server=None, name="particle1"):
        """Initialize the particle with a server reference"""
        self.server = server
        self.name = name
        self.initialized = False
        
        # We'll start with 2 oscillators for the initial implementation
        # OP1 (modulator) -> CAR1 (carrier)
        self.oscillators = {}
        
        # Only initialize if server is provided and running
        if self.server and self.server.getIsStarted():
            self.initialize()
    
    def initialize(self):
        """Initialize all oscillators and set up modulation routing"""
        if not self.server or not self.server.getIsStarted():
            self.initialized = False
            return False
        
        # Create the oscillators
        self.oscillators["OP1"] = Oscillator(self.server, "OP1", "operator")
        self.oscillators["CAR1"] = Oscillator(self.server, "CAR1", "carrier")
        
        # Initialize all oscillators
        for name, osc in self.oscillators.items():
            if not osc.initialized:
                osc.initialize()
        
        # Set up modulation routing - OP1 modulates CAR1
        op1 = self.oscillators.get("OP1")
        car1 = self.oscillators.get("CAR1")
        
        if op1 and car1 and op1.initialized and car1.initialized:
            # Get the modulation output from OP1
            mod_signal = op1.get_mod_output()
            if mod_signal:
                # Use default mod amount during initialization
                mod_amount = 100.0  # Default fallback value
                            
                # Apply modulation with default amount
                car1.apply_modulation(mod_signal, mod_amount)
        
        self.initialized = True
        return True
    
    def note_on(self, note, velocity, ui_dict):
        """Trigger note-on for all oscillators with UI parameters"""
        if not self.initialized:
            return
            
        # Get UI references for each oscillator
        for name, osc in self.oscillators.items():
            if name in ui_dict:
                # Trigger the note with the appropriate UI
                osc.note_on(note, velocity, ui_dict[name])
                
                # Special handling for modulation from O1 to C1
                if name == "CAR1" and "OP1" in self.oscillators:
                    # Try to get modulation amount from UI if available
                    mod_amount = 100.0  # Default fallback value
                    
                    # Get from UI if it has the parameter
                    if hasattr(ui_dict[name], "mod_amount"):
                        try:
                            mod_amount = ui_dict[name].mod_amount.itemAt(1).widget().value()
                        except Exception as e:
                            print(f"Error getting mod amount: {e}")
                    
                    # Get the modulation signal from OP1        
                    op1 = self.oscillators["OP1"]
                    if op1.initialized:
                        mod_signal = op1.get_mod_output()
                        if mod_signal:
                            # Apply updated modulation amount
                            osc.apply_modulation(mod_signal, mod_amount)
    
    def note_off(self, note):
        """Trigger note-off for all oscillators"""
        if not self.initialized:
            return
            
        for name, osc in self.oscillators.items():
            osc.note_off(note)
    
    def pitch_bend(self, value):
        """Apply pitch bend to all oscillators"""
        if not self.initialized:
            return
            
        for name, osc in self.oscillators.items():
            osc.pitch_bend(value)
    
    def shutdown(self):
        """Clean shutdown of all oscillators"""
        if not self.initialized:
            return
            
        for name, osc in self.oscillators.items():
            osc.shutdown()
            
        self.initialized = False
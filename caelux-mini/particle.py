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
        
        # Expanded to include OP1, CAR1, and CAR2 in the implementation
        # OP1 (modulator) can modulate both CAR1 and CAR2
        self.oscillators = {}
        
        # Routing matrix - dictionary of source -> list of (destination, amount) tuples
        self.modulation_matrix = {}
        
        # Channel output buses (uses all available channels, up to 4)
        self.output_buses = []
        # Limit to the actual number of available channels, up to a maximum of 4
        self.output_channels = min(4, self.server.getNchnls() if self.server else 2)
        print(f"Particle initialized with {self.output_channels} output channels")
        
        # Only initialize if server is provided and running
        if self.server and self.server.getIsStarted():
            self.initialize()
    
    def initialize(self):
        """Initialize all oscillators and set up modulation routing"""
        if not self.server or not self.server.getIsStarted():
            self.initialized = False
            return False
        
        # Create the output buses first
        self.output_buses = []
        
        # Update output_channels based on available channels
        self.output_channels = min(4, self.server.getNchnls())
        print(f"Initializing with {self.output_channels} output channels")
        
        # Use Mixer for output routing, with compatibility for different pyo versions
        try:
            # Try the newer pyo version first with outs and chnls parameters
            self.mixer = pyo.Mixer(outs=self.output_channels, chnls=2)  # 2 channels input, variable output
            print("Using pyo.Mixer with outs/chnls parameters")
        except TypeError:
            # Fall back to older pyo version that doesn't support outs/chnls
            print("Falling back to basic pyo.Mixer")
            self.mixer = pyo.Mixer(voices=self.output_channels, outs=self.output_channels)
            # Note: in older pyo, voices controls the number of inputs
        
        # Route mixer outputs directly to audio channels
        # In Pyo, the mixer automatically routes to output channels
        # Just store the indices for reference
        for i in range(self.output_channels):
            self.output_buses.append(i)
            
        # Make sure the mixer is active
        self.mixer.out()
        
        # Create the oscillators
        self.oscillators["OP1"] = Oscillator(self.server, "OP1", "operator")
        self.oscillators["CAR1"] = Oscillator(self.server, "CAR1", "carrier")
        self.oscillators["CAR2"] = Oscillator(self.server, "CAR2", "carrier")
        
        # Initialize all oscillators
        for name, osc in self.oscillators.items():
            if not osc.initialized:
                osc.initialize()
        
        # Set up default routing matrix
        self.modulation_matrix = {
            "OP1": [("CAR1", 100.0), ("CAR2", 100.0)],  # OP1 modulates both CAR1 and CAR2
            "CAR1": [],  # CAR1 doesn't modulate anything by default
            "CAR2": []   # CAR2 doesn't modulate anything by default
        }
        
        # Apply the modulation routing
        self.apply_modulation_matrix()
        
        # Print debug info about the oscillators
        for name, osc in self.oscillators.items():
            if osc and osc.initialized:
                print(f"Oscillator {name} is initialized and ready.")
                if hasattr(osc, 'direct_out'):
                    print(f" - {name} has direct output enabled")
                else:
                    print(f" - WARNING: {name} has no direct output")
            else:
                print(f"WARNING: Oscillator {name} is not properly initialized")
        
        # Connect the oscillators to the output mixer with default routing
        car1 = self.oscillators.get("CAR1")
        car2 = self.oscillators.get("CAR2")
        
        # Get channel count
        available_channels = self.server.getNchnls()
        print(f"Setting up default routing for carriers with {available_channels} available output channels:")
        print(f"CAR1 available and initialized: {car1 is not None and car1.initialized}")
        print(f"CAR2 available and initialized: {car2 is not None and car2.initialized}")
        
        # Multichannel routing based on available channels
        if car1 and car1.initialized:
            # Connect CAR1 to channel 0 (front left)
            print("Connecting CAR1 to channel 0 (front left)")
            self.set_channel_routing("CAR1", 0, 1.0)
            
            # If we have 4 channels, also route to channel 2 (rear left)
            if available_channels >= 4:
                print("Also connecting CAR1 to channel 2 (rear left)")
                self.set_channel_routing("CAR1", 2, 0.7)
                
        if car2 and car2.initialized:
            # Connect CAR2 to channel 1 (front right)
            print("Connecting CAR2 to channel 1 (front right)")
            self.set_channel_routing("CAR2", 1, 1.0)
            
            # If we have 4 channels, also route to channel 3 (rear right)
            if available_channels >= 4:
                print("Also connecting CAR2 to channel 3 (rear right)")
                self.set_channel_routing("CAR2", 3, 0.7)
                
        # Print final setup summary
        print(f"Audio routing configured with {self.output_channels} channels")
        
        self.initialized = True
        return True
    
    def apply_modulation_matrix(self):
        """Apply the current modulation matrix to all oscillators"""
        if not self.initialized:
            return
            
        # Get each oscillator's modulation signal
        mod_signals = {}
        for name, osc in self.oscillators.items():
            if osc.initialized:
                mod_signals[name] = osc.get_mod_output()
        
        # Apply new modulation based on the matrix
        for source_name, destinations in self.modulation_matrix.items():
            # Skip if the source doesn't have a valid mod signal
            if source_name not in mod_signals:
                continue
                
            # Get the modulation signal
            mod_signal = mod_signals[source_name]
            if not mod_signal:
                continue
                
            # Apply to each destination
            for dest_name, amount in destinations:
                dest_osc = self.oscillators.get(dest_name)
                if dest_osc and dest_osc.initialized:
                    dest_osc.apply_modulation(mod_signal, amount)
    
    def set_modulation(self, source, destination, amount):
        """Set a modulation routing in the matrix
        
        Args:
            source (str): Name of the source oscillator
            destination (str): Name of the destination oscillator
            amount (float): Modulation amount
        """
        if not self.initialized:
            return
        
        # Check if source and destination exist
        if source not in self.oscillators or destination not in self.oscillators:
            print(f"Invalid source or destination: {source} -> {destination}")
            return
            
        # Update modulation matrix
        if source not in self.modulation_matrix:
            self.modulation_matrix[source] = []
            
        # Remove any existing routing for this source-destination pair
        updated_destinations = [d for d in self.modulation_matrix[source] if d[0] != destination]
        
        # Add new routing if amount > 0
        if amount > 0:
            updated_destinations.append((destination, amount))
            
        self.modulation_matrix[source] = updated_destinations
        
        # Apply the updated matrix
        self.apply_modulation_matrix()
    
    def note_on(self, note, velocity, ui_dict):
        """Trigger note-on for all oscillators with UI parameters"""
        if not self.initialized:
            return
            
        # Debug
        print(f"Particle received note_on: note={note}, velocity={velocity}")
        
        # Trigger note-on for all oscillators
        for name, osc in self.oscillators.items():
            if name in ui_dict:
                print(f"Triggering note_on for {name}")
                # Trigger the note with the appropriate UI
                osc.note_on(note, velocity, ui_dict[name])
                
        # Apply modulations based on the current matrix and UI settings
        for source_name, destinations in self.modulation_matrix.items():
            source_osc = self.oscillators.get(source_name)
            if not source_osc or not source_osc.initialized:
                continue
                
            # Get the modulation signal
            mod_signal = source_osc.get_mod_output()
            if not mod_signal:
                continue
                
            # Apply to each destination with amount from UI if available
            for dest_name, default_amount in destinations:
                dest_osc = self.oscillators.get(dest_name)
                dest_ui = ui_dict.get(dest_name)
                
                if not dest_osc or not dest_osc.initialized:
                    continue
                    
                # Try to get mod amount from destination's UI if available
                mod_amount = default_amount
                
                # Get from UI if it has the source's modulation parameter
                if dest_ui and hasattr(dest_ui, f"{source_name.lower()}_mod_amount"):
                    try:
                        # Try to get from specific UI parameter for this source
                        mod_param = getattr(dest_ui, f"{source_name.lower()}_mod_amount")
                        mod_amount = mod_param.itemAt(1).widget().value()
                    except Exception as e:
                        # Fallback to generic mod_amount
                        if hasattr(dest_ui, "mod_amount"):
                            try:
                                mod_amount = dest_ui.mod_amount.itemAt(1).widget().value()
                            except Exception as e2:
                                print(f"Error getting mod amount: {e2}")
                
                # Apply modulation
                dest_osc.apply_modulation(mod_signal, mod_amount)
    
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
    
    def set_channel_routing(self, oscillator_name, channel, amount=1.0):
        """Route an oscillator to an output channel
        
        Args:
            oscillator_name (str): Name of the oscillator
            channel (int): Channel number (0-3 for quad setup)
            amount (float): Routing amount (0.0-1.0)
        """
        if not self.initialized:
            return
            
        # Update output_channels to match the server's current channel count
        # This allows dynamic adaptation when audio devices change
        self.output_channels = min(4, self.server.getNchnls())
        
        if oscillator_name not in self.oscillators:
            print(f"Oscillator {oscillator_name} not found")
            return
            
        # Check if the requested channel is available
        if not 0 <= channel < self.output_channels:
            print(f"Channel {channel} is not available - using fallback")
            # Fallback routing: channels 2,3 -> 0,1 if quad isn't available
            if channel >= 2 and self.output_channels <= 2:
                channel = channel % 2  # Map 2->0 and 3->1
                print(f"Remapped to channel {channel}")
            elif channel >= self.output_channels:
                print(f"Invalid channel number: {channel}, max is {self.output_channels-1}")
                return
            
        osc = self.oscillators[oscillator_name]
        if osc.initialized:
            # Update the routing in the oscillator
            channel_name = f"channel_{channel}"
            osc.add_routing(channel_name, amount)
            
            # For mixer approach:
            if hasattr(self, 'mixer') and hasattr(osc, 'stereo'):
                # Try both older and newer pyo Mixer API versions
                try:
                    # First attempt - Use modern pyo API
                    try:
                        self.mixer.delInput(channel, 0)  # New style: delInput(chnl, voice)
                        if amount > 0:
                            self.mixer.addInput(channel, osc.stereo)
                            self.mixer.setAmp(channel, 0, amount)
                        print(f"Using modern pyo.Mixer API for routing {oscillator_name} to channel {channel}")
                    except TypeError:
                        # Second attempt - Use older pyo API 
                        try:
                            self.mixer.delInput(channel)  # Old style: delInput(voice)
                            if amount > 0:
                                self.mixer.addInput(channel, osc.stereo)
                                self.mixer.setAmp(channel, 0, amount)
                            print(f"Using older pyo.Mixer API for routing {oscillator_name} to channel {channel}")
                        except Exception as e2:
                            print(f"Mixer routing failed with error: {e2}")
                            
                            # Final fallback - direct channel output
                            if amount > 0:
                                # Direct output to channel as fallback
                                direct_out = osc.stereo * amount
                                direct_out.out(chnl=channel)
                                
                                # Store reference to avoid garbage collection
                                if not hasattr(osc, 'direct_channel_outputs'):
                                    osc.direct_channel_outputs = {}
                                osc.direct_channel_outputs[channel] = direct_out
                                print(f"Using direct output for {oscillator_name} to channel {channel}")
                except Exception as e:
                    print(f"Error in channel routing: {e}")
                    
                    # Last resort - ensure direct output is enabled for carriers
                    if oscillator_name.startswith("CAR") and amount > 0:
                        try:
                            direct_out = osc.stereo * amount
                            direct_out.out(chnl=channel)
                            # Keep reference
                            if not hasattr(osc, 'emergency_outputs'):
                                osc.emergency_outputs = {}
                            osc.emergency_outputs[channel] = direct_out
                            print(f"Emergency direct output enabled for {oscillator_name} to channel {channel}")
                        except Exception as e3:
                            print(f"Emergency routing also failed: {e3}")
    
    def get_output_channels(self):
        """Return the number of output channels"""
        return self.output_channels
    
    def get_routing_matrix(self):
        """Return the current modulation routing matrix"""
        return self.modulation_matrix.copy()
    
    def set_all_modulation(self, routing_matrix):
        """Set the entire modulation routing matrix
        
        Args:
            routing_matrix (dict): Dictionary mapping source names to 
                                  lists of (destination, amount) tuples
        """
        if not self.initialized:
            return
            
        self.modulation_matrix = routing_matrix.copy()
        self.apply_modulation_matrix()
    
    def shutdown(self):
        """Clean shutdown of all oscillators and buses"""
        if not self.initialized:
            return
            
        # Shutdown oscillators
        for name, osc in self.oscillators.items():
            osc.shutdown()
        
        # Clear output buses
        self.output_buses = []
        
        # Stop and clear the mixer - be careful with the reference
        try:
            if hasattr(self, 'mixer') and self.mixer is not None:
                # Remove all inputs
                for i in range(self.output_channels):
                    try:
                        self.mixer.delInput(i)
                    except:
                        pass
                
                # Stop the output
                try:
                    self.mixer.stop()
                except:
                    pass
                
                self.mixer = None
        except:
            # If any errors happen, just clear the reference
            self.mixer = None
            
        self.initialized = False
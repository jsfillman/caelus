import numpy as np
from pyo import HarmTable, ChebyTable, SawTable, SquareTable
import os

class WaveformBank:
    """
    Manages a collection of wavetables for use with the OscBank object.
    Provides methods to create, access and manage different waveform types.
    """
    
    def __init__(self, server=None):
        self.tables = {}
        self.server = server  # Store server reference if provided
    
    def create_standard_tables(self):
        """Create a set of standard waveforms"""
        # Sine wave
        self.tables["sine"] = HarmTable([1])
        
        # Saw wave (using built-in tables)
        self.tables["saw"] = SawTable()
        
        # Square wave
        self.tables["square"] = SquareTable()
        
        # Triangle wave (using harmonics)
        tri_content = []
        for i in range(1, 20, 2):
            tri_content.append(1.0 / (i * i) * pow(-1, (i - 1) // 2))
        self.tables["triangle"] = HarmTable(tri_content)
        
        # Simple additive synthesis examples
        self.tables["octaves"] = HarmTable([1, 0, 0.3, 0, 0.2, 0, 0, 0, 0.1])
        self.tables["evens"] = HarmTable([1, 0, 0.4, 0, 0.2, 0, 0.1])
        self.tables["odds"] = HarmTable([1, 0.5, 0, 0.2, 0, 0.1])
        self.tables["organ"] = HarmTable([1, 0.5, 0.3, 0, 0.2, 0.1, 0, 0.1])
        
        # Some interesting spectra
        self.tables["formant1"] = HarmTable([1, 0, 0.3, 0, 0.2, 0, 0, 0, 0.1, 0, 0, 0, 0.3])
        self.tables["formant2"] = HarmTable([0, 0, 0, 0, 0.3, 0.2, 0, 0.1, 0, 0, 0.05])
        self.tables["brass"] = HarmTable([0, 0.75, 0.5, 0, 0.14, 0.5, 0, 0.12, 0.02])
        
        # Some Chebyshev polynomials (good for FM synthesis)
        self.tables["cheby1"] = ChebyTable([1, 0, 0.3, 0, 0.2, 0, 0.1, 0, 0.04])
        self.tables["cheby2"] = ChebyTable([0, 0, 0, 1, 0, 0.3, 0, 0.2, 0, 0.1])
        
        # Physical modeling inspired
        self.tables["plucked"] = HarmTable([1, 0.8, 0.6, 0.4, 0.2, 0.1, 0.05, 0.02])
        self.tables["clarinet"] = HarmTable([1, 0, 0.75, 0, 0.5, 0, 0.14, 0, 0.5])
        
        return self
        
    def add_custom_table(self, name, harmonics):
        """Add a custom harmonic table"""
        self.tables[name] = HarmTable(harmonics)
        
    def add_custom_wave(self, name, path):
        """Add a custom waveform from an audio file"""
        if os.path.exists(path):
            self.tables[name] = SndTable(path)
            return True
        return False
        
    def get_table(self, name):
        """Get a table by name"""
        return self.tables.get(name, self.tables["sine"])  # Default to sine
        
    def get_table_list(self):
        """Return a list of all available table names"""
        return list(self.tables.keys())
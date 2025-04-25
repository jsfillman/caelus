"""
Patch controller wrapper for Caelus.

This module provides a wrapper around the PatchController for patch management.
"""
import os
import yaml
import time
from typing import Dict, List, Any, Optional, Callable, Union

from PyQt6.QtCore import QObject, pyqtSignal as Signal
from pythonosc import udp_client

from lib.common.utils import LOG
from lib.common.patch_controller import PatchController
from lib.midi_osc.helpers import send_osc
from utils.logger import log_osc_message, CaelusLogger

class PatchControllerWrapper(QObject):
    """
    Wrapper for the PatchController that provides patch management functions.
    
    Responsibilities:
    - List available patches
    - Load patches
    - Save patches
    - Apply patch parameters to synths
    """
    
    # Signal emitted when a patch is loaded
    patch_loaded = Signal(str)  # (patch_name)
    
    # Signal emitted when there's an error
    error = Signal(str)  # (error_message)
    
    def __init__(
        self,
        presets_dir: str,
        osc_client: udp_client.SimpleUDPClient,
        router_name: str = "router"
    ):
        """
        Initialize the patch controller wrapper.
        
        Args:
            presets_dir: Directory containing synth presets
            osc_client: OSC client for sending messages
            router_name: Name of OSC router
        """
        super().__init__()
        
        # Store parameters
        self.presets_dir = presets_dir
        self.osc_client = osc_client
        self.router_name = router_name
        
        # Create logger for patch-specific operations
        self.logger = CaelusLogger("patch_controller")
        
        # Create patch controller
        self.patch_ctrl = PatchController(
            presets_dir=presets_dir,
            osc_client=osc_client,
            router_name=router_name
        )
        
        # Connect signals from patch controller
        self.patch_ctrl.patch_loaded.connect(self._on_patch_loaded)
        self.patch_ctrl.error.connect(self._on_error)
        
        # Current bank and patch
        self.current_bank = None
        self.current_patch = None
        
    def _on_patch_loaded(self, patch_name: str) -> None:
        """
        Handle patch loaded signal from patch controller.
        
        Args:
            patch_name: Name of the loaded patch
        """
        # Forward the signal
        self.patch_loaded.emit(patch_name)
        
    def _on_error(self, message: str) -> None:
        """
        Handle error signal from patch controller.
        
        Args:
            message: Error message
        """
        # Forward the signal
        self.error.emit(message)
        
    def list_patches(self, bank_name: str) -> List[str]:
        """
        List available patches for a bank.
        
        Args:
            bank_name: Name of the bank
            
        Returns:
            List of available patch names
        """
        try:
            # Update current bank
            self.current_bank = bank_name
            
            # Get patches directory
            patches_dir = os.path.join(self.presets_dir, bank_name, "patches")
            
            # Check if directory exists
            if not os.path.exists(patches_dir):
                LOG.warning(f"Patches directory not found: {patches_dir}")
                return []
                
            # Get all YAML files
            patches = []
            for file in os.listdir(patches_dir):
                if file.endswith(".yaml") or file.endswith(".yml"):
                    patch_name = os.path.splitext(file)[0]
                    patches.append(patch_name)
                    
            return sorted(patches)
        except Exception as e:
            LOG.error(f"Error listing patches: {e}")
            return []
    
    def get_patch_file_path(self, bank_name: str, patch_name: str) -> str:
        """
        Get the file path for a patch.
        
        Args:
            bank_name: Name of the bank
            patch_name: Name of the patch
            
        Returns:
            Full path to patch file
        """
        # Add .yaml extension if not present
        if not patch_name.endswith(".yaml") and not patch_name.endswith(".yml"):
            patch_name = f"{patch_name}.yaml"
            
        return os.path.join(self.presets_dir, bank_name, "patches", patch_name)
    
    def load_patch(self, bank_name: str, patch_file: str) -> bool:
        """
        Load a patch from file.
        
        Args:
            bank_name: Name of the bank
            patch_file: Path to patch file
            
        Returns:
            True if patch was loaded successfully, False otherwise
        """
        try:
            # Update current bank
            self.current_bank = bank_name
            
            # Update current patch
            self.current_patch = patch_file
            
            # Load patch using patch controller
            result = self.patch_ctrl.load_patch(bank_name, patch_file)
            
            # Return success
            return result
        except Exception as e:
            LOG.error(f"Error loading patch: {e}")
            self.error.emit(f"Error loading patch: {e}")
            return False
    
    def save_patch(self, bank_name: str, patch_name: str, patch_data: Dict[str, Any]) -> bool:
        """
        Save a patch to file.
        
        Args:
            bank_name: Name of the bank
            patch_name: Name of the patch
            patch_data: Patch data to save
            
        Returns:
            True if patch was saved successfully, False otherwise
        """
        try:
            # Update current bank
            self.current_bank = bank_name
            
            # Save patch using patch controller
            result = self.patch_ctrl.save_patch(bank_name, patch_name, patch_data)
            
            # Update current patch if saved successfully
            if result:
                patch_file = self.get_patch_file_path(bank_name, patch_name)
                self.current_patch = patch_file
                
            # Return success
            return result
        except Exception as e:
            LOG.error(f"Error saving patch: {e}")
            self.error.emit(f"Error saving patch: {e}")
            return False
    
    def apply_patch_parameter(self, param_name: str, value: Union[float, int, bool]) -> bool:
        """
        Apply a single parameter to the current synth.
        
        Args:
            param_name: Name of the parameter
            value: Parameter value
            
        Returns:
            True if parameter was applied successfully, False otherwise
        """
        try:
            # Normalize value if needed
            if isinstance(value, bool):
                value = 1.0 if value else 0.0
            elif isinstance(value, int):
                value = float(value)
                
            # Send parameter to synth using OSC
            LOG.info(f"Setting parameter: {param_name} = {value}")
            send_osc(self.osc_client, f"/{self.router_name}/param", [param_name, value])
            
            # Return success
            return True
        except Exception as e:
            LOG.error(f"Error applying parameter: {e}")
            return False
    
    def get_current_patch(self) -> Optional[Dict[str, Any]]:
        """
        Get the current patch data.
        
        Returns:
            Current patch data or None if no patch loaded
        """
        if not self.current_patch:
            return None
            
        try:
            # Load patch file
            with open(self.current_patch, 'r') as f:
                patch_data = yaml.safe_load(f)
                
            return patch_data
        except Exception as e:
            LOG.error(f"Error getting current patch: {e}")
            return None
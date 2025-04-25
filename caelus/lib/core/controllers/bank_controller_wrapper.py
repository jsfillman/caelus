"""
Bank controller wrapper for Caelus.

This module provides a wrapper around the BankController for bank management.
"""
import os
import subprocess
from typing import Dict, List, Any, Optional, Callable

from PyQt6.QtCore import QObject, pyqtSignal as Signal
from pythonosc import udp_client

from lib.common.utils import LOG
from lib.common.bank_controller import BankController
from utils.logger import log_osc_message, CaelusLogger

class BankControllerWrapper(QObject):
    """
    Wrapper for the BankController that provides bank management functions.
    
    Responsibilities:
    - List available synth banks
    - Load banks
    - Manage synth processes
    - Monitor synth connectivity
    """
    
    # Signal emitted when a bank is loaded
    bank_loaded = Signal(str, str)  # (bank_name, bank_dir)
    
    # Signal emitted when connectivity status changes
    connectivity_changed = Signal(int, int)  # (alive_synths, total_synths)
    
    def __init__(
        self,
        presets_dir: str,
        osc_ip: str = "127.0.0.1",
        osc_port: int = 9000,
        router_name: str = "router",
        ui_osc_port: int = 9002
    ):
        """
        Initialize the bank controller wrapper.
        
        Args:
            presets_dir: Directory containing synth presets
            osc_ip: IP address of OSC router
            osc_port: Port of OSC router
            router_name: Name of OSC router
            ui_osc_port: Port for UI OSC communication
        """
        super().__init__()
        
        # Store parameters
        self.presets_dir = presets_dir
        self.osc_ip = osc_ip
        self.osc_port = osc_port
        self.router_name = router_name
        self.ui_osc_port = ui_osc_port
        
        # Create logger for bank-specific operations
        self.logger = CaelusLogger("bank_controller")
        
        # Create bank controller
        self.bank_ctrl = BankController(
            presets_dir=presets_dir,
            osc_ip=osc_ip,
            osc_port=osc_port,
            router_name=router_name,
            ui_osc_port=ui_osc_port
        )
        
    def list_banks(self) -> List[str]:
        """
        List available synth banks.
        
        Returns:
            List of available bank names
        """
        try:
            return self.bank_ctrl.list_banks()
        except Exception as e:
            LOG.error(f"Error listing banks: {e}")
            return []
            
    def get_bank_directory(self, bank_name: str) -> str:
        """
        Get the directory path for a bank.
        
        Args:
            bank_name: Name of the bank
            
        Returns:
            Full path to bank directory
        """
        return os.path.join(self.presets_dir, bank_name)
    
    def load_bank(self, bank_name: str) -> Dict[str, int]:
        """
        Load a synth bank.
        
        Args:
            bank_name: Name of the bank to load
            
        Returns:
            Dictionary with counts of local and remote synths loaded
        """
        try:
            # Load the bank
            result = self.bank_ctrl.load_bank(bank_name)
            
            # Get bank directory
            bank_dir = self.get_bank_directory(bank_name)
            
            # Emit bank loaded signal
            self.bank_loaded.emit(bank_name, bank_dir)
            
            # Log bank loading
            LOG.info(f"Loaded bank '{bank_name}' with {result['local']} local and {result['remote']} remote synths")
            
            # Log OSC stats
            if hasattr(self.bank_ctrl, 'synth_processes'):
                for i, process in enumerate(self.bank_ctrl.synth_processes):
                    if process and hasattr(process, 'pid'):
                        LOG.info(f"Synth {i}: PID {process.pid}")
            
            # Return synth counts
            return result
        except Exception as e:
            LOG.error(f"Error loading bank: {e}")
            import traceback
            traceback.print_exc()
            return {"local": 0, "remote": 0}
    
    def check_synth_connectivity(self) -> Dict[str, int]:
        """
        Check connectivity status of synth processes.
        
        Returns:
            Dictionary with counts of alive and total synths
        """
        try:
            # Get synth processes from bank controller
            if not hasattr(self.bank_ctrl, 'synth_processes'):
                return {"alive": 0, "total": 0}
                
            total_synths = len(self.bank_ctrl.synth_processes)
            if total_synths == 0:
                return {"alive": 0, "total": 0}
                
            # Count alive processes
            alive_count = sum(1 for p in self.bank_ctrl.synth_processes if p.poll() is None)
            
            # Emit connectivity changed signal
            self.connectivity_changed.emit(alive_count, total_synths)
            
            LOG.info(f"Synth connectivity check: {alive_count}/{total_synths} synths connected")
            
            return {"alive": alive_count, "total": total_synths}
        except Exception as e:
            LOG.error(f"Error checking synth connectivity: {e}")
            return {"alive": 0, "total": 0}
    
    def get_synth_processes(self) -> List[subprocess.Popen]:
        """
        Get the current synth processes.
        
        Returns:
            List of subprocess.Popen objects for running synths
        """
        if hasattr(self.bank_ctrl, 'synth_processes'):
            return self.bank_ctrl.synth_processes
        return []
        
    def stop(self) -> None:
        """Stop all synth processes and clean up."""
        if hasattr(self.bank_ctrl, 'stop'):
            self.bank_ctrl.stop()
        elif hasattr(self.bank_ctrl, 'clean_up'):
            self.bank_ctrl.clean_up()
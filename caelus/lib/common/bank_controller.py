"""
BankController - Enumerates available synth banks and loads them.
"""
from typing import List, Dict
from lib.common.bank_manager import BankManager
from lib.common.bank_loader import BankLoader

class BankController:
    """
    Provides high-level bank operations for the UI:
    - list_banks()
    - load_bank(bank_name) -> {'local': int, 'remote': int}
    """
    def __init__(
        self,
        presets_dir: str,
        osc_ip: str,
        osc_port: int,
        router_name: str,
        ui_osc_port: int
    ) -> None:
        self.bank_manager = BankManager(presets_dir)
        self.bank_loader = BankLoader(
            presets_dir,
            osc_ip,
            osc_port,
            router_name,
            ui_osc_port
        )

    def list_banks(self) -> List[str]:
        """Return a list of available synth bank names."""
        return self.bank_manager.list_banks()

    def load_bank(self, bank_name: str) -> Dict[str, int]:
        """
        Load the given bank, spawning router and synths.

        Returns:
            Dict with counts: {'local': int, 'remote': int}
        """
        return self.bank_loader.load_bank(bank_name) 
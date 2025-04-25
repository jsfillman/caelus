"""
PatchController - Manages patch file I/O and applying patches over OSC.
"""
import os
from typing import Any, Dict, Optional
from PyQt6.QtCore import QObject, pyqtSignal
from pythonosc import udp_client
from lib.core.bank_manager import BankManager
from lib.midi_osc.helpers import send_osc

class PatchController(QObject):
    """
    Handles loading and saving patch files for synth banks,
    and applies loaded patches by sending OSC param messages.
    """
    # Emitted when a patch is successfully loaded (patch name)
    patch_loaded = pyqtSignal(str)
    # Emitted when an error occurs during patch load or save
    error = pyqtSignal(str)

    def __init__(
        self,
        presets_dir: str,
        osc_client: udp_client.SimpleUDPClient,
        router_name: str
    ) -> None:
        super().__init__()
        self.bank_manager = BankManager(presets_dir)
        self.osc_client = osc_client
        self.router_name = router_name

    def save_patch(
        self,
        bank_name: str,
        patch_name: str,
        patch_data: Dict[str, Any]
    ) -> Optional[str]:
        """
        Save patch_data to a YAML file under the bank's patches directory.

        Returns:
            Full path to saved patch or None on error.
        """
        try:
            path = self.bank_manager.save_patch(bank_name, patch_name, patch_data)
            return path
        except Exception as e:
            self.error.emit(str(e))
            return None

    def load_patch(
        self,
        bank_name: str,
        patch_file: str
    ) -> None:
        """
        Load a patch file and apply its parameters via OSC.

        Emits:
            patch_loaded with patch display name on success,
            error with error message on failure.
        """
        try:
            data = self.bank_manager.load_patch(bank_name, patch_file)
            if not isinstance(data, dict):
                raise ValueError("Loaded patch is not a valid dict")

            # Apply each param via OSC
            for param, value in data.items():
                if param.startswith('_'):
                    continue
                send_osc(
                    self.osc_client,
                    f"/{self.router_name}/param",
                    [param, float(value)]
                )
            # Determine patch name from metadata or filename
            name = os.path.basename(patch_file).replace('.yaml', '')
            meta = data.get('_metadata', {})
            if isinstance(meta, dict) and 'name' in meta:
                name = meta['name']
            self.patch_loaded.emit(name)
        except Exception as e:
            self.error.emit(str(e)) 
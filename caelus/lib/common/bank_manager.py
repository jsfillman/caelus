"""
BankManager - Handles listing, loading of synth banks and saving/loading of patches.
"""
import os
import yaml
from typing import Any, Dict, List, Optional, Tuple

class BankManager:
    """
    Provides methods to discover and load synth banks (directories with voices.yaml and synth binary),
    as well as managing patch files.
    """
    def __init__(self, presets_dir: str) -> None:
        """Initialize with the base presets directory."""
        self.presets_dir = presets_dir

    def list_banks(self) -> List[str]:
        """Return a list of available bank names (subdirectories)."""
        if not os.path.isdir(self.presets_dir):
            return []
        return [name for name in os.listdir(self.presets_dir)
                if os.path.isdir(os.path.join(self.presets_dir, name))]

    def load_bank(self, bank_name: str) -> Dict[str, Any]:
        """
        Load the bank's configuration from voices.yaml and locate synth binary.

        Args:
            bank_name: Name of the bank directory

        Returns:
            Dict with keys: 'bank_dir', 'config', 'voices_file', 'synth_file'

        Raises:
            FileNotFoundError: If required files or directories are missing.
        """
        bank_dir = os.path.join(self.presets_dir, bank_name)
        if not os.path.isdir(bank_dir):
            raise FileNotFoundError(f"Bank directory not found: {bank_dir}")

        voices_file = os.path.join(bank_dir, 'voices.yaml')
        synth_file = os.path.join(bank_dir, 'synth')
        if not os.path.isfile(voices_file):
            raise FileNotFoundError(f"Missing voices.yaml in {bank_dir}")
        if not os.path.isfile(synth_file):
            raise FileNotFoundError(f"Missing synth binary in {bank_dir}")

        with open(voices_file, 'r') as f:
            config = yaml.safe_load(f)

        return {
            'bank_dir': bank_dir,
            'config': config,
            'voices_file': voices_file,
            'synth_file': synth_file
        }

    def save_patch(self, bank_name: str, patch_name: str, patch_data: Dict[str, Any]) -> str:
        """
        Save a patch file under the bank's 'patches' subdirectory.

        Args:
            bank_name: Name of the bank
            patch_name: Filename (without .yaml)
            patch_data: Dictionary of patch parameters

        Returns:
            Full path to the saved patch file
        """
        bank_dir = os.path.join(self.presets_dir, bank_name)
        patches_dir = os.path.join(bank_dir, 'patches')
        os.makedirs(patches_dir, exist_ok=True)

        filename = patch_name if patch_name.endswith('.yaml') else patch_name + '.yaml'
        patch_path = os.path.join(patches_dir, filename)
        with open(patch_path, 'w') as f:
            yaml.dump(patch_data, f, default_flow_style=False)
        return patch_path

    def load_patch(self, bank_name: str, patch_file: str) -> Dict[str, Any]:
        """
        Load a patch YAML file and return its contents.

        Args:
            bank_name: Name of the bank (for path context)
            patch_file: Full path or name of the patch file

        Returns:
            Parsed patch dictionary
        """
        # If patch_file is not absolute, assume it's in bank/patches
        if not os.path.isabs(patch_file):
            bank_dir = os.path.join(self.presets_dir, bank_name)
            patch_file = os.path.join(bank_dir, 'patches', patch_file)
        if not os.path.isfile(patch_file):
            raise FileNotFoundError(f"Patch file not found: {patch_file}")

        with open(patch_file, 'r') as f:
            return yaml.safe_load(f) 
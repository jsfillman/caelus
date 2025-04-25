"""
Settings management for Caelus.

This module provides central settings management with defaults and configuration loading.
"""
import os
import yaml
from typing import Dict, Any, Optional

# Default application settings
DEFAULT_SETTINGS = {
    # Router settings
    "router_ip": "127.0.0.1",
    "router_port": 9000,
    "ui_port": 9002,
    
    # Paths
    "presets_dir": "presets",
    
    # UI settings
    "window_width": 2224,
    "window_height": 1668,
    "show_splash": True,
    
    # Default selections
    "default_bank": "00 - Simple Mono",
    "auto_select_first_midi": True,
    
    # Resources
    "splash_image": "Caelus.png",
    "app_icon": "CaelusAppIcon.png",
}

class Settings:
    """Central settings management for the application."""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize settings with optional configuration file.
        
        Args:
            config_file: Path to configuration file (YAML format)
        """
        self._settings = DEFAULT_SETTINGS.copy()
        
        # Load configuration file if provided
        if config_file and os.path.exists(config_file):
            self._load_config(config_file)
            
    def _load_config(self, config_file: str) -> None:
        """
        Load configuration from a YAML file.
        
        Args:
            config_file: Path to configuration file
        """
        try:
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
                
            if isinstance(config, dict):
                # Update settings with values from config file
                self._settings.update(config)
        except Exception as e:
            print(f"Error loading configuration file: {e}")
            
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a setting value.
        
        Args:
            key: Setting key
            default: Default value if key not found
            
        Returns:
            Setting value or default
        """
        return self._settings.get(key, default)
        
    def set(self, key: str, value: Any) -> None:
        """
        Set a setting value.
        
        Args:
            key: Setting key
            value: Setting value
        """
        self._settings[key] = value
        
    def update(self, settings: Dict[str, Any]) -> None:
        """
        Update multiple settings at once.
        
        Args:
            settings: Dictionary of settings to update
        """
        self._settings.update(settings)
        
    def all(self) -> Dict[str, Any]:
        """
        Get all settings.
        
        Returns:
            Dictionary of all settings
        """
        return self._settings.copy()
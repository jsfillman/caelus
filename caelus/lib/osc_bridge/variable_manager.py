"""
VariableManager - Manages getting and setting router variables via OSC paths.
"""
from typing import Any, Optional
from lib.common.utils import LOG

class VariableManager:
    """
    Manages getting and setting of router variables by path.
    """
    def __init__(self, router: 'OSCRouter') -> None:
        """Initialize the variable manager with reference to the OSCRouter."""
        self.router = router

    def set_variable(self, var_path: str, value: Any) -> bool:
        """
        Set a router variable by dot-separated path.

        Args:
            var_path: Variable path (e.g., 'voice_manager.default_cutoff')
            value: Value to set

        Returns:
            True if variable was set successfully, False otherwise.
        """
        try:
            parts = var_path.split('.')
            obj = self.router

            for part in parts[:-1]:
                if hasattr(obj, part):
                    obj = getattr(obj, part)
                else:
                    LOG.error(f"Path not found: {var_path}")
                    return False

            final_attr = parts[-1]
            if hasattr(obj, final_attr):
                current_value = getattr(obj, final_attr)
                new_value = self._convert_value(value, type(current_value))
                setattr(obj, final_attr, new_value)
                LOG.info(f"Set {var_path} = {new_value}")

                if var_path == 'voice_manager.default_cutoff':
                    self.router.voice_manager._update_filter_cutoff()
                return True

            LOG.error(f"Attribute not found: {final_attr}")
            return False
        except Exception as e:
            LOG.error(f"Error setting variable {var_path}: {e}")
            return False

    def get_variable(self, var_path: str) -> Optional[Any]:
        """
        Get a router variable by dot-separated path.

        Args:
            var_path: Variable path (e.g., 'voice_manager.default_cutoff')

        Returns:
            The variable value if found, None otherwise.
        """
        try:
            obj = self.router
            for part in var_path.split('.'):
                if hasattr(obj, part):
                    obj = getattr(obj, part)
                else:
                    LOG.error(f"Path not found: {var_path}")
                    return None

            LOG.info(f"Get {var_path} = {obj}")
            return obj
        except Exception as e:
            LOG.error(f"Error getting variable {var_path}: {e}")
            return None

    def _convert_value(self, value: Any, target_type: type) -> Any:
        """
        Convert a given value to the target type.
        """
        try:
            if isinstance(value, target_type):
                return value
            if target_type == int:
                return int(value)
            if target_type == float:
                return float(value)
            if target_type == bool:
                if isinstance(value, str):
                    return value.lower() in ('true', 'yes', '1')
                return bool(value)
            return str(value)
        except Exception as e:
            LOG.error(f"Error converting value {value} to {target_type}: {e}")
            return value 
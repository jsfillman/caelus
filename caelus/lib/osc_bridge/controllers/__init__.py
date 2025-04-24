"""
Router Controllers Package
Exports controller classes to wire up OSC address handlers.
"""
import pkgutil
import importlib
import os

# Registry for controllers
__all__ = []
CONTROLLERS = []

def register_controller(cls):
    """
    Decorator to register controller classes for OSC routing.
    """
    __all__.append(cls.__name__)
    CONTROLLERS.append(cls)
    return cls

# Dynamically import controller modules to populate CONTROLLERS
package_dir = os.path.dirname(__file__)
for _, module_name, _ in pkgutil.iter_modules([package_dir]):
    importlib.import_module(f".{module_name}", __name__) 
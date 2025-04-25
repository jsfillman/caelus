"""
Module loader for Caelus.

This module handles dynamic loading of Python modules from file paths.
"""
import os
import sys
import importlib.util
from typing import Any

class ModuleLoader:
    """Dynamic module loader for Python modules from file paths."""
    
    @staticmethod
    def load_module(module_path: str) -> Any:
        """
        Dynamically load a Python module from a file path.
        
        Args:
            module_path: Path to the Python module file
            
        Returns:
            Loaded module object
            
        Raises:
            ImportError: If the module cannot be loaded
        """
        if not os.path.exists(module_path):
            raise ImportError(f"Module path does not exist: {module_path}")
            
        module_name = os.path.basename(module_path).replace('.py', '')
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        
        if spec is None or spec.loader is None:
            raise ImportError(f"Failed to create module spec for: {module_path}")
            
        module = importlib.util.module_from_spec(spec)
        
        # Add current directory to path to resolve imports
        module_dir = os.path.dirname(module_path)
        sys.path.insert(0, module_dir)
        
        try:
            # Execute the module
            spec.loader.exec_module(module)
        finally:
            # Always remove the directory from path, even if an exception occurs
            if module_dir in sys.path:
                sys.path.remove(module_dir)
        
        return module
        
    @staticmethod
    def has_function(module: Any, function_name: str) -> bool:
        """
        Check if a module has a specified function.
        
        Args:
            module: Module object to check
            function_name: Name of the function to check for
            
        Returns:
            True if the module has the specified function, False otherwise
        """
        return hasattr(module, function_name) and callable(getattr(module, function_name))
        
    @staticmethod
    def call_function(module: Any, function_name: str, *args, **kwargs) -> Any:
        """
        Call a function in a module with the specified arguments.
        
        Args:
            module: Module object containing the function
            function_name: Name of the function to call
            *args: Positional arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function
            
        Returns:
            Result of the function call
            
        Raises:
            AttributeError: If the module does not have the specified function
        """
        if not ModuleLoader.has_function(module, function_name):
            raise AttributeError(f"Module does not have function: {function_name}")
            
        function = getattr(module, function_name)
        return function(*args, **kwargs)
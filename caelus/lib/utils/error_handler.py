"""
Error handling utilities for Caelus.

This module provides decorators and functions for consistent error handling.
"""
import sys
import traceback
import functools
from typing import Any, Callable, Dict, Optional, Type, TypeVar, cast

from lib.core.utils import LOG

# Type variable for decorator functions
F = TypeVar('F', bound=Callable[..., Any])

def log_exceptions(
    logger: Optional[Any] = None,
    level: str = "error",
    reraise: bool = True,
    message: Optional[str] = None
) -> Callable[[F], F]:
    """
    Decorator to log exceptions raised by a function.
    
    Args:
        logger: Logger to use (defaults to the global LOG)
        level: Log level to use ("error", "warning", etc.)
        reraise: Whether to reraise the exception after logging
        message: Custom message prefix to include with the error
        
    Returns:
        Decorated function
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Use the provided logger or the global logger
                log = logger or LOG
                
                # Build the error message
                error_message = message or f"Error in {func.__name__}:"
                error_message = f"{error_message} {str(e)}"
                
                # Get traceback information
                tb = traceback.format_exc()
                
                # Log the error
                if hasattr(log, level):
                    log_method = getattr(log, level)
                    log_method(error_message)
                    log_method(tb)
                
                # Reraise if requested
                if reraise:
                    raise
                    
                return None
                
        return cast(F, wrapper)
    return decorator

def handle_ui_exceptions(
    show_dialog: bool = True,
    status_update: Optional[Callable[[str, str], None]] = None
) -> Callable[[F], F]:
    """
    Decorator to handle exceptions in UI code.
    
    Args:
        show_dialog: Whether to show an error dialog
        status_update: Optional function to update a status display
        
    Returns:
        Decorated function
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Log the error
                error_message = f"UI Error in {func.__name__}: {str(e)}"
                LOG.error(error_message)
                LOG.error(traceback.format_exc())
                
                # Update status if provided
                if status_update:
                    status_update("error", f"Error: {str(e)}")
                
                # Show error dialog if requested
                if show_dialog:
                    try:
                        from PyQt6.QtWidgets import QMessageBox
                        QMessageBox.critical(None, "Error", error_message)
                    except ImportError:
                        # If PyQt is not available, just log
                        LOG.error("Could not show error dialog (PyQt not available)")
                        
                return None
                
        return cast(F, wrapper)
    return decorator

def safe_call(func: Callable, *args: Any, **kwargs: Any) -> Optional[Any]:
    """
    Safely call a function, catching any exceptions.
    
    Args:
        func: Function to call
        *args: Arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function
        
    Returns:
        Function result or None if an exception occurred
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        LOG.error(f"Error calling {func.__name__}: {str(e)}")
        LOG.error(traceback.format_exc())
        return None
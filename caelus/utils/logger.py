"""
Enhanced logging utilities for Caelus.

This module provides enhanced logging utilities for Caelus, including OSC message tracking.
"""
import os
import sys
import logging
import datetime
from typing import Dict, Any, Optional, List, Union

# Default log level
DEFAULT_LOG_LEVEL = logging.INFO

# Log format
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Global flag for OSC message logging
osc_message_logging_enabled = False

class CaelusLogger:
    """Enhanced logger with OSC message tracking."""
    
    def __init__(
        self, 
        name: str = "caelus", 
        level: int = DEFAULT_LOG_LEVEL,
        log_to_file: bool = False,
        log_dir: str = "logs",
        max_file_size: int = 10 * 1024 * 1024,  # 10 MB
        max_backup_count: int = 5
    ):
        """
        Initialize the Caelus logger.
        
        Args:
            name: Logger name
            level: Log level
            log_to_file: Whether to log to file
            log_dir: Directory for log files
            max_file_size: Maximum size of log files in bytes
            max_backup_count: Maximum number of backup log files
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # Create formatter
        formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
        
        # Create console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # Create file handler if enabled
        if log_to_file:
            try:
                # Create log directory if it doesn't exist
                if not os.path.exists(log_dir):
                    os.makedirs(log_dir)
                
                # Create timestamped log file
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                log_file = os.path.join(log_dir, f"caelus_{timestamp}.log")
                
                # Create file handler with rotation
                from logging.handlers import RotatingFileHandler
                file_handler = RotatingFileHandler(
                    log_file,
                    maxBytes=max_file_size,
                    backupCount=max_backup_count
                )
                file_handler.setFormatter(formatter)
                self.logger.addHandler(file_handler)
                
                self.logger.info(f"Logging to file: {log_file}")
            except Exception as e:
                self.logger.error(f"Failed to set up file logging: {e}")
        
        # OSC message tracking
        self.osc_message_logging_enabled = osc_message_logging_enabled
        
    def enable_osc_logging(self) -> None:
        """Enable OSC message logging."""
        global osc_message_logging_enabled
        osc_message_logging_enabled = True
        self.osc_message_logging_enabled = True
        self.logger.info("OSC message logging enabled")
        
    def disable_osc_logging(self) -> None:
        """Disable OSC message logging."""
        global osc_message_logging_enabled
        osc_message_logging_enabled = False
        self.osc_message_logging_enabled = False
        self.logger.info("OSC message logging disabled")
        
    def log_osc_message(
        self, 
        direction: str,
        address: str, 
        args: List[Any], 
        host: str = "N/A", 
        port: Union[int, str] = "N/A"
    ) -> None:
        """
        Log an OSC message if OSC logging is enabled.
        
        Args:
            direction: "SEND" or "RECV" to indicate message direction
            address: OSC address
            args: OSC arguments
            host: Host IP address
            port: Port number
        """
        if not self.osc_message_logging_enabled:
            return
            
        # Format message for logging
        message = f"OSC {direction}: {address} {args} -> {host}:{port}"
        
        # Log at debug level to avoid cluttering normal logs
        self.logger.debug(message)
    
    # Forward standard logging methods
    def debug(self, message: str) -> None:
        """Log a debug message."""
        self.logger.debug(message)
        
    def info(self, message: str) -> None:
        """Log an info message."""
        self.logger.info(message)
        
    def warning(self, message: str) -> None:
        """Log a warning message."""
        self.logger.warning(message)
        
    def error(self, message: str) -> None:
        """Log an error message."""
        self.logger.error(message)
        
    def critical(self, message: str) -> None:
        """Log a critical message."""
        self.logger.critical(message)
        
    def exception(self, message: str) -> None:
        """Log an exception message with traceback."""
        self.logger.exception(message)


# Create a default logger instance
LOG = CaelusLogger()

# Function to enable OSC message logging globally
def enable_osc_logging() -> None:
    """Enable OSC message logging globally."""
    LOG.enable_osc_logging()
    
# Function to disable OSC message logging globally
def disable_osc_logging() -> None:
    """Disable OSC message logging globally."""
    LOG.disable_osc_logging()
    
# Function to log an OSC message
def log_osc_message(
    direction: str,
    address: str, 
    args: List[Any], 
    host: str = "N/A", 
    port: Union[int, str] = "N/A"
) -> None:
    """
    Log an OSC message if OSC logging is enabled.
    
    Args:
        direction: "SEND" or "RECV" to indicate message direction
        address: OSC address
        args: OSC arguments
        host: Host IP address
        port: Port number
    """
    LOG.log_osc_message(direction, address, args, host, port)
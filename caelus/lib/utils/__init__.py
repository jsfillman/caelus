"""
Utils module for Caelus. Contains utility functions and classes.
"""

from lib.utils.logger import CaelusLogger, LOG, enable_osc_logging
from lib.utils.settings import Settings
from lib.utils.error_handler import log_exceptions, handle_ui_exceptions, safe_call
from lib.utils.module_loader import ModuleLoader
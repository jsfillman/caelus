"""
Core module for Caelus. Contains core functionality and base components.
"""

# Import core components from merged common module
from lib.core.utils import LOG, midi_to_freq
from lib.core.bank_controller import BankController
from lib.core.bank_loader import BankLoader
from lib.core.bank_manager import BankManager
from lib.core.patch_controller import PatchController
from lib.core.connectivity_controller import ConnectivityController
from lib.core.launcher_gui import LauncherGUI
from lib.core.synth_process_manager import SynthProcessManager

# Import original core components
from lib.core.app import CaelusApp
from lib.core.launcher import CaelusLauncher
from lib.core.splash import SplashManager
from lib.core.connectivity import ConnectivityMonitor
from lib.core.activity_monitor import ActivityMonitor
from lib.core.argparser import parse_args, get_settings_from_args
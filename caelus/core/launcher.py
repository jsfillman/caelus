"""
Core launcher component for Caelus.

This module provides the launcher functionality that integrates all components.
"""
import os
import sys
import time
from typing import Dict, List, Any, Optional

from lib.common.utils import LOG
from utils.settings import Settings
from utils.logger import enable_osc_logging

from core.app import CaelusApp
from core.splash import SplashManager
from core.connectivity import ConnectivityMonitor
from core.activity_monitor import ActivityMonitor

from core.controllers.midi_controller_wrapper import MidiControllerWrapper
from core.controllers.bank_controller_wrapper import BankControllerWrapper
from core.controllers.patch_controller_wrapper import PatchControllerWrapper

from ui.main_window import MainWindow
from ui.tabs.midi_tab import MidiTab
from ui.tabs.bank_tab import BankTab

from pythonosc import udp_client

class CaelusLauncher:
    """
    Main launcher for Caelus that integrates all components.
    
    Responsibilities:
    - Initialize core components
    - Create and configure controllers
    - Setup UI
    - Coordinate startup sequence
    """
    
    def __init__(self, settings: Settings):
        """
        Initialize the launcher with settings.
        
        Args:
            settings: Application settings
        """
        self.settings = settings
        
        # Enable OSC logging if debug is enabled
        if self.settings.get("debug", False):
            enable_osc_logging()
            LOG.info("OSC message logging enabled")
        
        # Create main application
        self.app = CaelusApp(settings)
        
        # Create OSC client for controllers
        self.osc_client = udp_client.SimpleUDPClient(
            settings.get("router_ip", "127.0.0.1"),
            settings.get("router_port", 9000)
        )
        
        # Create controllers
        self._create_controllers()
        
        # Create monitors
        self._create_monitors()
        
        # Initialize components
        self.initialized = False
    
    def _create_controllers(self) -> None:
        """Create controller wrappers."""
        # MIDI controller
        self.midi_controller = MidiControllerWrapper(
            osc_client=self.osc_client,
            router_name=self.settings.get("router_name", "router")
        )
        
        # Bank controller
        self.bank_controller = BankControllerWrapper(
            presets_dir=self.settings.get("presets_dir", "presets"),
            osc_ip=self.settings.get("router_ip", "127.0.0.1"),
            osc_port=self.settings.get("router_port", 9000),
            router_name=self.settings.get("router_name", "router"),
            ui_osc_port=self.settings.get("ui_port", 9002)
        )
        
        # Patch controller
        self.patch_controller = PatchControllerWrapper(
            presets_dir=self.settings.get("presets_dir", "presets"),
            osc_client=self.osc_client,
            router_name=self.settings.get("router_name", "router")
        )
    
    def _create_monitors(self) -> None:
        """Create activity and connectivity monitors."""
        # Create activity monitor
        self.activity_monitor = ActivityMonitor(
            flash_interval=self.settings.get("flash_interval", 100)
        )
        
        # Create connectivity monitor
        self.connectivity_monitor = ConnectivityMonitor(
            check_interval=self.settings.get("connectivity_check_interval", 30000)
        )
    
    def initialize(self) -> None:
        """Initialize all components."""
        # Start the router
        self.app.start_router()
        
        # Initialize UI
        self._initialize_ui()
        
        # Setup signal connections
        self._setup_signals()
        
        # Directly trigger the default bank loading after a short delay
        # This ensures that the UI is completely set up before loading
        from PyQt6.QtCore import QTimer
        default_bank = self.settings.get("default_bank")
        if default_bank:
            from lib.common.utils import LOG
            LOG.info(f"Setting up launcher timer to load default bank: {default_bank}")
            QTimer.singleShot(2000, self._load_default_bank)
            
        # Mark as initialized
        self.initialized = True
    
    def _initialize_ui(self) -> None:
        """Initialize UI components."""
        # Initialize main window
        self.app.start_gui()
        
        # Create tab components
        self._create_tabs()
        
        # Add tabs to main window
        self._setup_main_window()
    
    def _create_tabs(self) -> None:
        """Create tab components."""
        # MIDI tab
        self.midi_tab = MidiTab(
            midi_controller=self.midi_controller,
            auto_select_first_port=self.settings.get("auto_select_first_midi", True),
            refresh_interval=self.settings.get("midi_refresh_interval", 3000)
        )
        
        # Bank tab
        self.bank_tab = BankTab(
            bank_controller=self.bank_controller,
            patch_controller=self.patch_controller,
            default_bank=self.settings.get("default_bank")
        )
    
    def _setup_main_window(self) -> None:
        """Setup the main window with tabs."""
        if hasattr(self.app, 'main_window') and self.app.main_window:
            # Get main window
            main_window = self.app.main_window
            
            # Add tabs
            main_window.tab_widget.addTab(self.midi_tab, "MIDI")
            main_window.tab_widget.addTab(self.bank_tab, "Synth")
            
            # Set current tab
            main_window.tab_widget.setCurrentIndex(0)
    
    def _setup_signals(self) -> None:
        """Connect signals between components."""
        # Connect activity signals
        self.midi_tab.midi_activity.connect(self.activity_monitor.register_midi_activity)
        self.activity_monitor.midi_activity.connect(self.midi_tab.update_midi_light)
        self.activity_monitor.osc_activity.connect(self.midi_tab.update_osc_light)
        
        # Connect bank loaded signal
        self.bank_tab.bank_loaded.connect(self._on_bank_loaded)
        
        # Connect connectivity signal
        self.connectivity_monitor.connectivity_changed.connect(self.bank_tab._on_connectivity_changed)
    
    def _on_bank_loaded(self, bank_name: str, bank_dir: str) -> None:
        """
        Handle bank loaded event.
        
        Args:
            bank_name: Name of the loaded bank
            bank_dir: Full path to the bank directory
        """
        from lib.common.utils import LOG
        LOG.info(f"Launcher._on_bank_loaded called with bank={bank_name}, dir={bank_dir}")
        
        # Start monitoring synth processes
        synth_processes = self.bank_controller.get_synth_processes()
        LOG.info(f"Got {len(synth_processes)} synth processes to monitor")
        self.connectivity_monitor.update_processes(synth_processes)
        
        # Update UI with bank info
        if hasattr(self.app, 'main_window') and self.app.main_window:
            LOG.info(f"Calling main_window.set_synth_ui with bank={bank_name}")
            result = self.app.main_window.set_synth_ui(bank_name, bank_dir)
            LOG.info(f"set_synth_ui result: {result}")
            
            # Switch to bank tab
            LOG.info("Switching to bank tab")
            self.app.main_window.tab_widget.setCurrentIndex(1)
        else:
            LOG.warning("Cannot update UI - main_window not available")
    
    def _load_default_bank(self) -> None:
        """Directly load the default bank from the launcher."""
        from lib.common.utils import LOG
        
        try:
            # Get default bank from settings
            default_bank = self.settings.get("default_bank")
            if not default_bank:
                LOG.warning("No default bank specified in settings")
                return
                
            LOG.info(f"Launcher directly loading default bank: {default_bank}")
            
            # Check if bank exists in list of available banks
            banks = self.bank_controller.list_banks()
            if default_bank not in banks:
                LOG.warning(f"Default bank '{default_bank}' not found in available banks: {banks}")
                return
                
            # Get bank directory
            bank_dir = self.bank_controller.get_bank_directory(default_bank)
            LOG.info(f"Bank directory: {bank_dir}")
            
            # Load the bank directly via the bank controller
            LOG.info(f"Loading bank via bank controller: {default_bank}")
            result = self.bank_controller.load_bank(default_bank)
            
            LOG.info(f"Bank loaded: {result}")
            
            # Directly call _on_bank_loaded to ensure UI updates
            LOG.info("Directly calling _on_bank_loaded to update UI")
            self._on_bank_loaded(default_bank, bank_dir)
            
            LOG.info("Default bank loading complete")
        except Exception as e:
            LOG.error(f"Error loading default bank: {e}")
    
    def run(self) -> int:
        """
        Run the application.
        
        Returns:
            Exit code
        """
        if not self.initialized:
            self.initialize()
            
        # Run the application
        LOG.info("Running Caelus application")
        return self.app.run()
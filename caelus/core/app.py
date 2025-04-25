"""
Core application class for Caelus.

This module provides the main application class that handles the application lifecycle.
"""
import os
import sys
import time
from typing import Optional, Dict, Any, List

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

from lib.common.utils import LOG
from lib.osc_bridge.router import OSCRouter
from lib.common.launcher_gui import LauncherGUI

from core.splash import SplashManager
from ui.main_window import MainWindow
from utils.settings import Settings

class CaelusApp:
    """
    Main application class for Caelus.
    
    Handles:
    - Application initialization and lifecycle
    - Component coordination
    - Router and UI startup
    """
    
    def __init__(self, settings: Settings):
        """
        Initialize the application with settings.
        
        Args:
            settings: Application settings
        """
        self.settings = settings
        
        # Create Qt application
        self.app = QApplication(sys.argv)
        
        # Set application icon
        icon_path = settings.get("app_icon")
        if icon_path and os.path.exists(icon_path):
            app_icon = QIcon(icon_path)
            self.app.setWindowIcon(app_icon)
            LOG.info(f"Set application icon from {icon_path}")
        
        # Initialize splash screen if enabled
        self.splash_manager = None
        if settings.get("show_splash"):
            self.splash_manager = SplashManager(settings.get("splash_image"))
            self.splash = self.splash_manager.show_splash(self.app)
        
        # Initialize components
        self.router: Optional[OSCRouter] = None
        self.main_window: Optional[MainWindow] = None
        self.gui: Optional[LauncherGUI] = None
    
    def _initialize_router(self) -> None:
        """Initialize the OSC router."""
        if self.splash_manager:
            self.splash_manager.update_message("Starting synth router...")
        
        # Create router instance
        self.router = OSCRouter(
            router_port=self.settings.get("router_port"),
            ui_host="127.0.0.1", 
            ui_port=self.settings.get("ui_port")
        )
    
    def _start_router_process(self) -> None:
        """Start the router in a background thread."""
        if self.router:
            self.router.start_in_background()
            time.sleep(0.5)  # Give router time to initialize
    
    def start_router(self) -> None:
        """Initialize and start the OSC router."""
        # Check if we should skip starting the router
        if self.settings.get("no_auto_start_router", False):
            LOG.info("Skipping router auto-start (no_auto_start_router flag is set)")
            return
            
        self._initialize_router()
        self._start_router_process()
    
    def _initialize_main_window(self) -> None:
        """Initialize the main application window."""
        # Create main window
        self.main_window = MainWindow(
            title="Caelus Synthesizer",
            width=self.settings.get("window_width"),
            height=self.settings.get("window_height"),
            icon_path=self.settings.get("app_icon")
        )
    
    def _initialize_gui_components(self) -> None:
        """Initialize the launcher GUI components."""
        if self.splash_manager:
            self.splash_manager.update_message("Starting MIDI interface...")
        
        # Create GUI
        self.gui = LauncherGUI(
            osc_ip=self.settings.get("router_ip"),
            osc_port=self.settings.get("router_port"),
            router_name="router",
            presets_dir=self.settings.get("presets_dir"),
            ui_osc_port=self.settings.get("ui_port"),
            auto_select_first_interface=self.settings.get("auto_select_first_midi"),
            default_bank=self.settings.get("default_bank"),
            on_bank_loaded=self._on_bank_loaded,
            parent=self.main_window.global_tab
        )
        
        # Add GUI to the main window
        self.main_window.set_global_widget(self.gui)
    
    def start_gui(self) -> None:
        """Initialize and start the GUI components."""
        self._initialize_main_window()
        self._initialize_gui_components()
        
        # Show main window
        self.main_window.show()
        
        # Close splash screen once GUI is shown
        if self.splash_manager:
            self.splash_manager.finish(self.main_window)
    
    def _on_bank_loaded(self, bank_name: str, bank_dir: str) -> None:
        """
        Handle bank loaded event from LauncherGUI.
        
        Args:
            bank_name: Name of the loaded bank
            bank_dir: Full path to the bank directory
        """
        # Load the synth UI using the main window's methods
        if self.main_window:
            self.main_window.set_synth_ui(bank_name, bank_dir)
    
    def run(self) -> int:
        """
        Run the application.
        
        Returns:
            Exit code
        """
        # Start router
        self.start_router()
        
        # Start GUI
        self.start_gui()
        
        # Run the event loop
        return self.app.exec()
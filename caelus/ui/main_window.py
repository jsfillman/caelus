"""
Main window for Caelus.

This module handles the main application window and tab management.
"""
import os
from typing import Optional, Dict, Any, Callable

from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout
)
from PyQt6.QtGui import QIcon

from lib.common.utils import LOG
from utils.module_loader import ModuleLoader

class MainWindow(QMainWindow):
    """Main application window for Caelus."""
    
    def __init__(
        self, 
        title: str = "Caelus Synthesizer",
        width: int = 2224, 
        height: int = 1668,
        icon_path: Optional[str] = None
    ):
        """
        Initialize the main window.
        
        Args:
            title: Window title
            width: Window width
            height: Window height
            icon_path: Path to application icon
        """
        super().__init__()
        
        self.setWindowTitle(title)
        self.resize(width, height)
        
        # Set application icon if provided
        if icon_path and os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            LOG.info(f"Set application icon from {icon_path}")
        
        # Create tab widget for tab management
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)
        
        # Global controls tab
        self.global_tab = QWidget()
        self.global_layout = QVBoxLayout(self.global_tab)
        self.tab_widget.addTab(self.global_tab, "Global")
        
        # Synth tab (will be populated when a bank is loaded)
        self.synth_tab = QWidget()
        self.synth_layout = QVBoxLayout(self.synth_tab)
        self.synth_layout.addWidget(QWidget())  # Placeholder
        self.tab_widget.addTab(self.synth_tab, "Synth")
        
        # Ensure Global tab is selected at startup
        self.tab_widget.setCurrentIndex(0)
        
        # Reference to the currently loaded synth UI module
        self.current_synth_ui = None
    
    def set_global_widget(self, widget: QWidget) -> None:
        """
        Set the widget for the global tab.
        
        Args:
            widget: Widget to set as the global tab content
        """
        # Clear existing widgets
        for i in reversed(range(self.global_layout.count())):
            item = self.global_layout.itemAt(i)
            if item.widget():
                item.widget().setParent(None)
        
        # Add the new widget
        self.global_layout.addWidget(widget)
    
    def set_synth_ui(self, bank_name: str, bank_dir: str, on_ui_loaded: Optional[Callable] = None) -> bool:
        """
        Load and set the UI for a synth bank.
        
        Args:
            bank_name: Name of the bank
            bank_dir: Directory containing the bank
            on_ui_loaded: Callback function when UI is loaded
            
        Returns:
            True if UI was loaded successfully, False otherwise
        """
        # Clear the current UI
        self._clear_synth_ui()
        
        # Check if the bank has a UI module
        ui_path = os.path.join(bank_dir, "ui.py")
        LOG.info(f"Looking for UI module at: {ui_path}")
        
        if not os.path.exists(ui_path):
            LOG.error(f"No UI module found at: {ui_path}")
            self.tab_widget.setTabText(1, "Synth: None")
            return False
        
        try:
            # Load the UI module using the module loader
            LOG.info(f"Loading UI module from: {ui_path}")
            ui_module = ModuleLoader.load_module(ui_path)
            
            # Check if the module has a create_ui_widget function
            if ModuleLoader.has_function(ui_module, 'create_ui_widget'):
                LOG.info(f"Found create_ui_widget function in {ui_path}")
                
                # Create the UI widget
                LOG.info("Creating synth UI widget...")
                synth_ui = ui_module.create_ui_widget()
                LOG.info("Synth UI widget created successfully")
                
                # Remove placeholder and add the synth UI
                LOG.info("Clearing existing synth layout")
                for i in reversed(range(self.synth_layout.count())): 
                    if self.synth_layout.itemAt(i).widget():
                        self.synth_layout.itemAt(i).widget().setParent(None)
                
                # Add the synth UI
                LOG.info("Adding new synth UI to layout")
                self.synth_layout.addWidget(synth_ui)
                self.current_synth_ui = synth_ui
                
                # Update tab text with bank name
                LOG.info(f"Updating tab text to: Synth: {bank_name}")
                self.tab_widget.setTabText(1, f"Synth: {bank_name}")
                
                # Switch to the synth tab
                LOG.info("Switching to synth tab")
                self.tab_widget.setCurrentIndex(1)
                
                LOG.info(f"Loaded synth UI for bank: {bank_name}")
                
                # Call the callback if provided
                if on_ui_loaded:
                    LOG.info("Calling on_ui_loaded callback")
                    on_ui_loaded(synth_ui)
                    
                return True
            else:
                LOG.warning(f"UI module does not have create_ui_widget function: {ui_path}")
                self.tab_widget.setTabText(1, f"Synth: {bank_name} (No UI)")
                return False
                
        except Exception as e:
            LOG.error(f"Error loading UI module: {e}")
            self.tab_widget.setTabText(1, f"Synth: {bank_name} (Error)")
            return False
    
    def _clear_synth_ui(self) -> None:
        """Clear the current synth UI from the synth tab."""
        if self.current_synth_ui:
            self.current_synth_ui.setParent(None)
            self.current_synth_ui = None
            
            # Add a placeholder widget
            self.synth_layout.addWidget(QWidget())
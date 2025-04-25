"""
Bank tab for Caelus.

This module provides a tab for synth bank and patch management.
"""
from typing import Optional, List, Dict, Any, Callable
import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel
)
from PyQt6.QtCore import Qt, pyqtSignal as Signal

from lib.core.utils import LOG
from lib.core.controllers.bank_controller_wrapper import BankControllerWrapper
from lib.core.controllers.patch_controller_wrapper import PatchControllerWrapper
from lib.ui.tabs.base_tab import BaseTab
from lib.ui.widgets.status_display import StatusDisplay
from lib.ui.widgets.bank_selector import BankSelector
from lib.ui.widgets.patch_manager import PatchManager

class BankTab(BaseTab):
    """
    Tab for synth bank and patch management.
    
    Features:
    - Bank selection dropdown
    - Bank loading button
    - Patch selection, loading, and saving
    - Synth connectivity status
    """
    
    # Signal emitted when a bank is loaded
    bank_loaded = Signal(str, str)  # (bank_name, bank_dir)
    
    # Signal emitted when a patch is loaded
    patch_loaded = Signal(str)  # (patch_name)
    
    def __init__(
        self,
        bank_controller: BankControllerWrapper,
        patch_controller: PatchControllerWrapper,
        default_bank: Optional[str] = None,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize the bank tab.
        
        Args:
            bank_controller: Bank controller wrapper
            patch_controller: Patch controller wrapper
            default_bank: Default bank to load (if any)
            parent: Parent widget
        """
        # Store parameters first so they're available to _setup_ui()
        self.bank_controller = bank_controller
        self.patch_controller = patch_controller
        self.default_bank = default_bank
        
        # Call parent init (which calls _setup_ui)
        super().__init__(parent)
        
        # Set tab name
        self.tab_name = "Synth Banks"
        
        # Connect signals
        self._setup_signals()
        
        # Auto-load default bank if specified
        if self.default_bank:
            # Use PyQt timer to load after UI is initialized
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(1000, self._auto_load_default_bank)
    
    def _setup_ui(self) -> None:
        """Set up the user interface."""
        # Use BaseTab's _setup_ui() to create the layout
        super()._setup_ui()
        
        # Verify layout_obj exists
        if not hasattr(self, 'layout_obj'):
            raise RuntimeError("BaseTab._setup_ui() did not create layout_obj")
            
        # Header section
        header_label = QLabel("Synth Bank and Patch Control")
        header_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFA500;")
        self.layout_obj.addWidget(header_label)
        
        # Status display
        self.status_display = StatusDisplay(
            initial_text="Ready",
            initial_color="#00FF00",  # Green
            font_size=14
        )
        self.layout_obj.addWidget(self.status_display)
        
        # Bank selector
        self.bank_selector = BankSelector(
            bank_controller=self.bank_controller,
            status_display=self.status_display,
            default_bank=self.default_bank
        )
        self.layout_obj.addWidget(self.bank_selector)
        
        # Patch manager
        self.patch_manager = PatchManager(
            patch_controller=self.patch_controller,
            status_display=self.status_display
        )
        self.layout_obj.addWidget(self.patch_manager)
        
        # Add spacer at the bottom
        self.layout_obj.addStretch()
    
    def _setup_signals(self) -> None:
        """Connect signals between components."""
        # Connect bank selector signals
        self.bank_selector.bank_loaded.connect(self._on_bank_loaded)
        
        # Connect patch manager signals
        self.patch_manager.patch_loaded.connect(self._on_patch_loaded)
        
        # Connect controller signals
        self.bank_controller.connectivity_changed.connect(self._on_connectivity_changed)
    
    def _on_bank_loaded(self, bank_name: str, bank_dir: str) -> None:
        """
        Handle bank loaded event.
        
        Args:
            bank_name: Name of the loaded bank
            bank_dir: Full path to the bank directory
        """
        # Refresh patch list
        self.patch_manager.refresh_patch_list(bank_name)
        
        # Emit signal
        self.bank_loaded.emit(bank_name, bank_dir)
    
    def _on_patch_loaded(self, patch_name: str) -> None:
        """
        Handle patch loaded event.
        
        Args:
            patch_name: Name of the loaded patch
        """
        # Emit signal
        self.patch_loaded.emit(patch_name)
    
    def _on_connectivity_changed(self, alive_count: int, total_count: int) -> None:
        """
        Handle connectivity changed signal from bank controller.
        
        Args:
            alive_count: Number of alive synths
            total_count: Total number of synths
        """
        if alive_count == 0 and total_count > 0:
            # No synths alive
            self.status_display.update_status("error", f"WARNING: No synths connected (0/{total_count})")
        elif alive_count < total_count:
            # Some synths alive
            self.status_display.update_status("warning", f"Partial connection: {alive_count}/{total_count} synths")
        elif total_count > 0:
            # All synths alive
            self.status_display.update_status("info", f"Connected: {alive_count}/{total_count} synths")
    
    def on_tab_activated(self) -> None:
        """Handle tab activation event."""
        super().on_tab_activated()
        
        # Refresh bank list
        self.bank_selector.refresh_bank_list()
    
    def _auto_load_default_bank(self) -> None:
        """Automatically load the default bank if specified."""
        from lib.core.utils import LOG
        if not self.default_bank:
            return
            
        LOG.info(f"Bank tab auto-loading default bank: {self.default_bank}")
        
        try:
            # Check if bank selector exists and is initialized
            if hasattr(self, 'bank_selector') and self.bank_selector is not None:
                LOG.info("Bank selector found, continuing with load")
                
                # Get list of available banks to verify default is valid
                banks = self.bank_controller.list_banks()
                LOG.info(f"Available banks: {banks}")
                
                if self.default_bank in banks:
                    LOG.info(f"Default bank '{self.default_bank}' is available")
                    
                    # Get bank directory
                    bank_dir = self.bank_controller.get_bank_directory(self.default_bank)
                    LOG.info(f"Bank directory: {bank_dir}")
                    
                    # Load the bank directly via the bank controller
                    LOG.info(f"Loading bank via bank controller: {self.default_bank}")
                    result = self.bank_controller.load_bank(self.default_bank)
                    
                    LOG.info(f"Bank loaded: {result}")
                    
                    # Important: Manually call our own _on_bank_loaded to ensure signals get emitted
                    LOG.info("Calling _on_bank_loaded to ensure UI updates")
                    self._on_bank_loaded(self.default_bank, bank_dir)
                    
                    LOG.info("Bank auto-load completed successfully")
                else:
                    LOG.warning(f"Default bank '{self.default_bank}' not found in available banks")
        except Exception as e:
            LOG.warning(f"Error in BankTab auto-loading default bank: {e}")
            
    def reset(self) -> None:
        """Reset tab to default state."""
        # Reset status
        self.status_display.update_status("info", "Ready")
        
        # Refresh bank list
        self.bank_selector.refresh_bank_list()
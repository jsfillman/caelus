"""
Bank selector widget for Caelus.

This module provides a widget for selecting and loading synth banks.
"""
from typing import Optional, List, Callable
import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QComboBox, QPushButton, QLabel,
    QMessageBox
)
from PyQt6.QtCore import pyqtSignal as Signal

from lib.common.utils import LOG
from core.controllers.bank_controller_wrapper import BankControllerWrapper
from ui.widgets.status_display import StatusDisplay

class BankSelector(QWidget):
    """
    Widget for selecting and loading synth banks.
    
    Features:
    - Bank dropdown
    - Load button
    - Auto-loading of default bank
    """
    
    # Signal emitted when bank selection changes
    bank_selected = Signal(str)  # (bank_name)
    
    # Signal emitted when a bank is loaded
    bank_loaded = Signal(str, str)  # (bank_name, bank_dir)
    
    def __init__(
        self,
        bank_controller: BankControllerWrapper,
        status_display: StatusDisplay,
        default_bank: Optional[str] = None,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize the bank selector widget.
        
        Args:
            bank_controller: Bank controller wrapper
            status_display: Status display widget for feedback
            default_bank: Default bank to load (if any)
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Store parameters
        self.bank_controller = bank_controller
        self.status_display = status_display
        self.default_bank = default_bank
        
        # Current bank
        self.current_bank = None
        
        # Initialize UI
        self._setup_ui()
        
        # Refresh bank list
        self.refresh_bank_list()
        
        # Connect bank controller signals
        self.bank_controller.bank_loaded.connect(self._on_bank_loaded)
        
        # Auto-load default bank if specified
        if self.default_bank:
            # Use small delay to ensure bank list is populated
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(500, self._load_default_bank)
    
    def _setup_ui(self) -> None:
        """Set up the user interface."""
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Bank label
        bank_label = QLabel("Synth Bank:")
        bank_label.setStyleSheet("font-size: 14px; color: #CCCCCC;")
        layout.addWidget(bank_label)
        
        # Bank dropdown
        self.bank_dropdown = QComboBox()
        self.bank_dropdown.setStyleSheet("""
            QComboBox { 
                background-color: #222; 
                color: #CCCCCC;
                border: 1px solid #FFA500; 
                padding: 6px; 
            }
        """)
        self.bank_dropdown.currentIndexChanged.connect(self._on_bank_selected)
        layout.addWidget(self.bank_dropdown)
        
        # Bank load button
        self.load_bank_btn = QPushButton("Load Bank")
        self.load_bank_btn.setStyleSheet("""
            QPushButton { 
                background-color: #222; 
                color: #CCCCCC;
                border: 1px solid #FFA500; 
                padding: 8px; 
            }
            QPushButton:hover { 
                background-color: #333; 
            }
            QPushButton:disabled {
                color: #666666;
                border-color: #666666;
            }
        """)
        self.load_bank_btn.clicked.connect(self._load_selected_bank)
        layout.addWidget(self.load_bank_btn)
    
    def refresh_bank_list(self) -> None:
        """Refresh the list of available synth banks."""
        # Clear dropdown
        self.bank_dropdown.clear()
        
        # Add placeholder item
        self.bank_dropdown.addItem("-- Select Synth --")
        
        try:
            # Get available banks
            banks = self.bank_controller.list_banks()
            
            if banks:
                # Add banks to dropdown
                self.bank_dropdown.addItems(banks)
                
                # Select current bank if any
                if self.current_bank and self.current_bank in banks:
                    self.bank_dropdown.setCurrentText(self.current_bank)
            else:
                LOG.warning("No synth banks found")
                self.status_display.update_status("warning", "No synth banks found")
        except Exception as e:
            LOG.error(f"Error listing banks: {e}")
            self.status_display.update_status("error", f"Error listing banks: {e}")
    
    def _load_default_bank(self) -> None:
        """Load the default bank if specified."""
        if not self.default_bank:
            return
            
        # Check if the bank is already loaded
        if self.current_bank == self.default_bank:
            LOG.info(f"Default bank '{self.default_bank}' is already loaded, skipping auto-load")
            return
            
        LOG.info(f"Auto-loading default bank: {self.default_bank}")
        
        # Find the index of the default bank in the dropdown
        index = self.bank_dropdown.findText(self.default_bank)
        if index >= 0:
            # Block signals to prevent double loading via _on_bank_selected
            self.bank_dropdown.blockSignals(True)
            
            # Select the bank in the dropdown
            self.bank_dropdown.setCurrentIndex(index)
            
            # Unblock signals
            self.bank_dropdown.blockSignals(False)
            
            # Load the bank directly
            self._load_selected_bank()
        else:
            LOG.warning(f"Default bank '{self.default_bank}' not found in bank list")
            self.status_display.update_status("warning", f"Default bank '{self.default_bank}' not found")
    
    def _on_bank_selected(self, index: int) -> None:
        """
        Handle bank selection from dropdown.
        
        Args:
            index: Index of selected bank in dropdown
        """
        if index <= 0:  # Skip the "-- Select Synth --" entry
            self.load_bank_btn.setEnabled(False)
            return
            
        # Get bank name
        bank_name = self.bank_dropdown.currentText()
        LOG.info(f"Selected bank: {bank_name}")
        
        # Enable load button
        self.load_bank_btn.setEnabled(True)
        
        # Emit bank selected signal
        self.bank_selected.emit(bank_name)
        
        # Only show load confirmation for manual selections, not auto-loads
        # Compare to default_bank to determine if this is an auto-load
        if bank_name != self.default_bank or self.default_bank is None:
            # Ask user if they want to load the bank
            response = QMessageBox.question(
                self,
                "Load Bank",
                f"Do you want to load the bank '{bank_name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if response == QMessageBox.StandardButton.Yes:
                # Load the bank
                self._load_selected_bank()
        else:
            # Auto-load without prompting for default bank
            self._load_selected_bank()
    
    def _load_selected_bank(self) -> None:
        """Load the currently selected synth bank."""
        # Get bank name
        bank_name = self.bank_dropdown.currentText()
        
        if not bank_name or bank_name == "-- Select Synth --":
            LOG.warning("No valid bank selected")
            self.status_display.update_status("warning", "Please select a synth bank first")
            return
            
        # Update current bank
        self.current_bank = bank_name
        
        # Update status
        self.status_display.update_status("info", f"Loading bank: {bank_name}...")
        
        try:
            # Load the bank
            result = self.bank_controller.load_bank(bank_name)
            
            # Update status
            self.status_display.update_status(
                "info", 
                f"Loaded bank '{bank_name}' with {result['local']} local and {result['remote']} remote synths"
            )
            
            # Get bank directory
            bank_dir = self.bank_controller.get_bank_directory(bank_name)
            
            # Emit signal (will also be emitted via the _on_bank_loaded handler)
            self.bank_loaded.emit(bank_name, bank_dir)
        except Exception as e:
            LOG.error(f"Error loading bank: {e}")
            self.status_display.update_status("error", f"Error loading bank: {e}")
    
    def _on_bank_loaded(self, bank_name: str, bank_dir: str) -> None:
        """
        Handle bank loaded signal from bank controller.
        
        Args:
            bank_name: Name of the loaded bank
            bank_dir: Full path to the bank directory
        """
        # Update current bank
        self.current_bank = bank_name
        
        # Forward the signal
        self.bank_loaded.emit(bank_name, bank_dir)
    
    def get_current_bank(self) -> Optional[str]:
        """
        Get the name of the currently selected bank.
        
        Returns:
            Current bank name or None if no bank selected
        """
        return self.current_bank
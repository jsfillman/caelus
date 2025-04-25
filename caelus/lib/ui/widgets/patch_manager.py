"""
Patch manager widget for Caelus.

This module provides a widget for loading and saving patches.
"""
from typing import Optional, List, Dict, Any, Callable
import os
import time

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QFileDialog
)
from PyQt6.QtCore import pyqtSignal as Signal

from lib.core.utils import LOG
from lib.core.controllers.patch_controller_wrapper import PatchControllerWrapper
from lib.ui.widgets.status_display import StatusDisplay

class PatchManager(QWidget):
    """
    Widget for managing synth patches.
    
    Features:
    - Patch dropdown
    - Load/save buttons
    - Panic button
    """
    
    # Signal emitted when a patch is loaded
    patch_loaded = Signal(str)  # (patch_name)
    
    def __init__(
        self,
        patch_controller: PatchControllerWrapper,
        status_display: StatusDisplay,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize the patch manager widget.
        
        Args:
            patch_controller: Patch controller wrapper
            status_display: Status display widget for feedback
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Store parameters
        self.patch_controller = patch_controller
        self.status_display = status_display
        
        # Current patch
        self.current_patch = None
        
        # Initialize UI
        self._setup_ui()
        
        # Connect patch controller signals
        self.patch_controller.patch_loaded.connect(self._on_patch_loaded)
        self.patch_controller.error.connect(self._on_patch_error)
        
        # Initially disable buttons until a bank is loaded
        self._update_button_state(False)
    
    def _setup_ui(self) -> None:
        """Set up the user interface."""
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Patch label
        patch_label = QLabel("Patch:")
        patch_label.setStyleSheet("font-size: 14px; color: #CCCCCC;")
        layout.addWidget(patch_label)
        
        # Patch dropdown
        self.patch_dropdown = QComboBox()
        self.patch_dropdown.setStyleSheet("""
            QComboBox { 
                background-color: #222; 
                color: #CCCCCC;
                border: 1px solid #FFA500; 
                padding: 6px; 
            }
            QComboBox:disabled {
                color: #666666;
                border-color: #666666;
            }
        """)
        layout.addWidget(self.patch_dropdown)
        
        # Patch buttons
        button_layout = QHBoxLayout()
        
        # Load patch button
        self.load_patch_btn = QPushButton("Load Patch")
        self.load_patch_btn.setStyleSheet("""
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
        self.load_patch_btn.clicked.connect(self._load_patch)
        button_layout.addWidget(self.load_patch_btn)
        
        # Save patch button
        self.save_patch_btn = QPushButton("Save Patch")
        self.save_patch_btn.setStyleSheet("""
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
        self.save_patch_btn.clicked.connect(self._save_patch)
        button_layout.addWidget(self.save_patch_btn)
        
        # Panic button
        self.panic_btn = QPushButton("PANIC")
        self.panic_btn.setStyleSheet("""
            QPushButton { 
                background-color: #550000; 
                color: #FFFFFF;
                border: 1px solid #FF0000; 
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover { 
                background-color: #770000; 
            }
            QPushButton:disabled {
                color: #666666;
                border-color: #666666;
                background-color: #331111;
            }
        """)
        self.panic_btn.clicked.connect(self._panic)
        button_layout.addWidget(self.panic_btn)
        
        layout.addLayout(button_layout)
    
    def refresh_patch_list(self, bank_name: str) -> None:
        """
        Refresh the list of available patches for a bank.
        
        Args:
            bank_name: Name of the bank
        """
        # Clear dropdown
        self.patch_dropdown.clear()
        
        try:
            # Get available patches
            patches = self.patch_controller.list_patches(bank_name)
            
            if patches:
                # Add patches to dropdown
                self.patch_dropdown.addItems(patches)
                
                # Select current patch if any
                if self.current_patch:
                    patch_name = os.path.basename(self.current_patch).replace('.yaml', '')
                    if patch_name in patches:
                        self.patch_dropdown.setCurrentText(patch_name)
                        
                # Enable buttons
                self._update_button_state(True)
            else:
                LOG.warning(f"No patches found for bank: {bank_name}")
                self.patch_dropdown.addItem("-- No patches found --")
                
                # Still enable buttons for creating new patches
                self._update_button_state(True)
        except Exception as e:
            LOG.error(f"Error listing patches: {e}")
            self.patch_dropdown.addItem("-- Error listing patches --")
            
            # Disable buttons
            self._update_button_state(False)
    
    def _load_patch(self) -> None:
        """Load the currently selected patch."""
        bank_name = self.patch_controller.current_bank
        if not bank_name:
            self.status_display.update_status("warning", "Please select a bank first")
            return
            
        # Get patch directory
        patches_dir = os.path.join(
            self.patch_controller.presets_dir, 
            bank_name, 
            "patches"
        )
        
        # Check if directory exists
        if not os.path.exists(patches_dir):
            os.makedirs(patches_dir)
            
        # If patch selected in dropdown, load it
        patch_name = self.patch_dropdown.currentText()
        if patch_name and patch_name not in ["-- No patches found --", "-- Error listing patches --"]:
            # Get patch file path
            patch_file = os.path.join(patches_dir, f"{patch_name}.yaml")
            
            # Load the patch
            try:
                self.patch_controller.load_patch(bank_name, patch_file)
                self.current_patch = patch_file
                return
            except Exception as e:
                LOG.error(f"Error loading patch: {e}")
                # Fall through to file dialog
        
        # Otherwise, show file dialog
        filename, _ = QFileDialog.getOpenFileName(
            self, "Load Patch", patches_dir, "YAML Files (*.yaml *.yml)"
        )
        
        if filename:
            try:
                # Load the patch
                self.patch_controller.load_patch(bank_name, filename)
                self.current_patch = filename
                
                # Update patch dropdown
                patch_name = os.path.basename(filename).replace('.yaml', '')
                index = self.patch_dropdown.findText(patch_name)
                if index >= 0:
                    self.patch_dropdown.setCurrentIndex(index)
            except Exception as e:
                LOG.error(f"Error loading patch from file: {e}")
                self.status_display.update_status("error", f"Error loading patch: {e}")
    
    def _save_patch(self) -> None:
        """Save the current synth state to a patch file."""
        bank_name = self.patch_controller.current_bank
        if not bank_name:
            self.status_display.update_status("warning", "Please select a bank first")
            return
            
        # Get patch directory
        patches_dir = os.path.join(
            self.patch_controller.presets_dir, 
            bank_name, 
            "patches"
        )
        
        # Check if directory exists
        if not os.path.exists(patches_dir):
            os.makedirs(patches_dir)
            
        # Show file dialog
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Patch", patches_dir, "YAML Files (*.yaml)"
        )
        
        if not filename:
            return
            
        # Add .yaml extension if not present
        if not filename.endswith('.yaml'):
            filename += '.yaml'
            
        # Get patch name
        patch_name = os.path.basename(filename).replace('.yaml', '')
        
        # For now, create a simple patch template
        # In a real implementation, you'd query the synth for current parameter values
        patch_data = {
            "_metadata": {
                "name": patch_name,
                "author": "Caelus User",
                "description": "Saved patch",
                "created": time.strftime("%Y-%m-%d %H:%M:%S")
            },
            "cutoff": 1000.0,
            "resonance": 0.5,
            "attack": 0.01,
            "decay": 0.1,
            "sustain": 0.7,
            "release": 0.5,
            "gain": 0.8
        }
        
        try:
            # Save the patch
            self.patch_controller.save_patch(bank_name, patch_name, patch_data)
            
            # Update current patch
            self.current_patch = filename
            
            # Refresh patch list
            self.refresh_patch_list(bank_name)
            
            # Select the new patch
            index = self.patch_dropdown.findText(patch_name)
            if index >= 0:
                self.patch_dropdown.setCurrentIndex(index)
                
            # Update status
            self.status_display.update_status("info", f"Saved patch: {patch_name}")
            
            # Emit signal
            self.patch_loaded.emit(patch_name)
        except Exception as e:
            LOG.error(f"Error saving patch: {e}")
            self.status_display.update_status("error", f"Error saving patch: {e}")
    
    def _panic(self) -> None:
        """
        Send all notes off message to all synths.
        
        This is the "panic button" functionality to clear stuck notes.
        """
        try:
            # Use the send_panic method from MIDI controller wrapper if available
            if hasattr(self.patch_controller.osc_client, 'send_panic'):
                self.patch_controller.osc_client.send_panic()
            else:
                # Otherwise, send all_notes_off directly
                from lib.midi_osc.helpers import send_osc
                send_osc(
                    self.patch_controller.osc_client, 
                    f"/{self.patch_controller.router_name}/all_notes_off", 
                    []
                )
                
            # Update status
            self.status_display.update_status("info", "All notes off - PANIC button pressed")
        except Exception as e:
            LOG.error(f"Error sending panic message: {e}")
            self.status_display.update_status("error", f"Error: {e}")
    
    def _update_button_state(self, enabled: bool) -> None:
        """
        Enable or disable buttons based on bank selection state.
        
        Args:
            enabled: Whether buttons should be enabled
        """
        self.load_patch_btn.setEnabled(enabled)
        self.save_patch_btn.setEnabled(enabled)
        self.panic_btn.setEnabled(enabled)
        self.patch_dropdown.setEnabled(enabled)
    
    def _on_patch_loaded(self, patch_name: str) -> None:
        """
        Handle patch loaded signal from patch controller.
        
        Args:
            patch_name: Name of the loaded patch
        """
        # Update status
        self.status_display.update_status("info", f"Loaded patch: {patch_name}")
        
        # Emit signal
        self.patch_loaded.emit(patch_name)
    
    def _on_patch_error(self, message: str) -> None:
        """
        Handle patch error signal from patch controller.
        
        Args:
            message: Error message
        """
        # Update status
        self.status_display.update_status("error", message)
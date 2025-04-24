#!/usr/bin/env python3
"""
Template for synth UI that uses a custom app icon.
This file can be copied to ui.py in a preset directory.
"""
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt

from lib.common.utils import set_app_icon, LOG

class SynthUI(QWidget):
    """Main widget for the synth UI, can be embedded or used standalone."""
    
    def __init__(self, parent=None):
        """Initialize the UI."""
        super().__init__(parent)
        
        # Create layout
        layout = QVBoxLayout(self)
        
        # Add UI elements
        title_label = QLabel("Caelus Synth UI")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 24pt; font-weight: bold;")
        layout.addWidget(title_label)
        
        # Add more synth-specific UI controls here
        # ...

def create_ui_widget(parent=None):
    """
    Create the UI widget for embedding in the main launcher.
    
    Args:
        parent: Optional parent widget
        
    Returns:
        The synth UI widget
    """
    return SynthUI(parent)

class StandaloneSynthUI(QMainWindow):
    """Standalone window for running the synth UI independently."""
    
    def __init__(self):
        """Initialize the standalone UI."""
        super().__init__()
        
        # Set window properties
        self.setWindowTitle("Caelus Synth UI")
        self.resize(2224, 1668)  # iPad dimensions
        
        # Create central widget
        central_widget = create_ui_widget()
        self.setCentralWidget(central_widget)
        
        # Add status bar
        self.statusBar().showMessage("Synth UI ready")

def main():
    """Main entry point for the synth UI when run standalone."""
    app = QApplication(sys.argv)
    
    # Set custom app icon if available
    set_app_icon(app)
    
    # Create and show the standalone UI
    window = StandaloneSynthUI()
    window.show()
    
    # Enter the application main loop
    return app.exec() if hasattr(app, 'exec') else app.exec_()

if __name__ == "__main__":
    sys.exit(main()) 
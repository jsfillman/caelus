"""
Splash screen manager for Caelus.

This module handles the splash screen display during application startup.
"""
from PyQt6.QtWidgets import QSplashScreen, QWidget
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt, QTimer
from typing import Optional

# Default splash image path
DEFAULT_SPLASH_IMAGE = "Caelus.png"

class SplashManager:
    """Manager for application splash screen display and lifecycle."""
    
    def __init__(self, splash_image_path: str = DEFAULT_SPLASH_IMAGE):
        """
        Initialize the splash screen manager.
        
        Args:
            splash_image_path: Path to the splash screen image
        """
        self.splash_image_path = splash_image_path
        self.splash: Optional[QSplashScreen] = None
        
    def show_splash(self, app) -> QSplashScreen:
        """
        Create and display the splash screen.
        
        Args:
            app: QApplication instance for processing events
            
        Returns:
            Initialized splash screen object
        """
        splash_pixmap = QPixmap(self.splash_image_path)
        self.splash = QSplashScreen(splash_pixmap, Qt.WindowType.WindowStaysOnTopHint)
        self.splash.setEnabled(False)
        self.splash.show()
        self.update_message("Initializing Caelus...")
        app.processEvents()
        return self.splash
    
    def update_message(self, message: str) -> None:
        """
        Update the splash screen message.
        
        Args:
            message: Message to display on the splash screen
        """
        if self.splash:
            self.splash.showMessage(
                message, 
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom, 
                Qt.GlobalColor.white
            )
    
    def finish(self, main_window: QWidget) -> None:
        """
        Close the splash screen once the main window is displayed.
        
        Args:
            main_window: Main application window that is ready to show
        """
        if self.splash:
            self.splash.finish(main_window)
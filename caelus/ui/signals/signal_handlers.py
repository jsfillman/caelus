"""
Signal handler classes for Caelus UI components.

This module provides signal handler classes for thread-safe communication
between OSC server threads, UI threads, and other components.
"""
from typing import Optional
from PyQt6.QtCore import QObject, pyqtSignal as Signal

class OSCSignalHandler(QObject):
    """
    Handler for OSC signals that communicates with the GUI.
    
    Signals:
        status_updated: Signal emitted when a status message is received (status_type, message)
        param_changed: Signal emitted when a parameter is changed (param_name, value)
    """
    status_updated = Signal(str, str)  # (status_type, message)
    param_changed = Signal(str, float)  # (param_name, value)

class UISignalHandler(QObject):
    """
    Handler for thread-safe UI updates.
    
    Signals:
        midi_light_update: Signal emitted when MIDI activity occurs (active)
        osc_light_update: Signal emitted when OSC activity occurs (active)
        status_update: Signal emitted when status needs to be updated (color, text)
    """
    midi_light_update = Signal(bool)  # (active)
    osc_light_update = Signal(bool)  # (active)
    status_update = Signal(str, str)  # (color, text)
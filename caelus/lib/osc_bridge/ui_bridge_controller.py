"""
UiBridgeController - Receives OSC messages from router for UI feedback and re-emits Qt signals.
"""
import threading
import time
from typing import Any
from PyQt6.QtCore import QObject, pyqtSignal
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer

class UiBridgeController(QObject):
    """
    Wraps a ThreadingOSCUDPServer to listen for /ui/status and /ui/param,
    emitting Qt signals for the GUI to consume.
    """
    status_updated = pyqtSignal(str, str)
    param_changed = pyqtSignal(str, float)

    def __init__(self, listen_port: int = 9002) -> None:
        super().__init__()
        self.listen_port = listen_port
        self.dispatcher = Dispatcher()
        self.dispatcher.map('/ui/status', self._on_status)
        self.dispatcher.map('/ui/param', self._on_param)
        self._server = ThreadingOSCUDPServer(('0.0.0.0', self.listen_port), self.dispatcher)
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._running = False

    def start(self) -> None:
        """Start listening for OSC UI feedback messages."""
        self._running = True
        self._thread.start()

    def stop(self) -> None:
        """Stop the OSC server."""
        self._running = False
        try:
            self._server.server_close()
        except Exception:
            pass

    def _serve(self) -> None:
        """Internal serve loop."""
        while self._running:
            try:
                self._server.handle_request()
            except Exception:
                time.sleep(0.1)

    def _on_status(self, address: str, status_type: str, message: str) -> None:
        """Handle /ui/status messages."""
        self.status_updated.emit(status_type, message)

    def _on_param(self, address: str, param_name: str, value: Any) -> None:
        """Handle /ui/param messages."""
        try:
            self.param_changed.emit(param_name, float(value))
        except Exception:
            pass 
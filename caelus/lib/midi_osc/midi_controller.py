"""
MidiController - Handles MIDI port enumeration, worker lifecycle, and event dispatch.
"""
from typing import List
from PyQt6.QtCore import QObject, pyqtSignal
from lib.midi_osc.midi_worker import MidiWorker
from mido import get_input_names

class MidiController(QObject):
    """
    Enumerates MIDI ports, manages MidiWorker, and emits signals on MIDI events.
    """
    # Emitted when a MIDI event arrives (raw mido message)
    midi_event = pyqtSignal(object)
    # Emitted to blink the MIDI activity light
    midi_light_update = pyqtSignal(bool)

    def __init__(self) -> None:
        super().__init__()
        self.worker: MidiWorker | None = None

    def list_ports(self) -> List[str]:
        """Return the list of available MIDI input port names."""
        try:
            return get_input_names()
        except Exception:
            return []

    def start(self, port_name: str) -> None:
        """Start the MIDI worker listening on the given port."""
        self.stop()
        self.worker = MidiWorker(port_name, self._on_midi)
        self.worker.start()

    def stop(self) -> None:
        """Stop the MIDI worker if running."""
        if self.worker:
            self.worker.stop()
            self.worker = None

    def _on_midi(self, msg) -> None:
        """Internal callback from MidiWorker for each incoming message."""
        # Blink MIDI light
        self.midi_light_update.emit(True)
        # Forward raw message for handling
        self.midi_event.emit(msg) 
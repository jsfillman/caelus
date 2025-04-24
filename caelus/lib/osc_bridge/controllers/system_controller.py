"""
SystemController - Maps system-level OSC endpoints to OSCRouter handlers.
"""
from pythonosc.dispatcher import Dispatcher
from lib.osc_bridge.router import OSCRouter
from . import register_controller

@register_controller
class SystemController:
    """
    Registers handlers for panic, all-notes-off, voice reset, and wildcard debugging.
    """
    def __init__(self, router: OSCRouter, dispatcher: Dispatcher) -> None:
        dispatcher.map("/router/all_notes_off", router.handle_all_notes_off)
        dispatcher.map("/router/voice/reset", router.handle_voice_reset)
        # Wildcard debug handler
        dispatcher.map("/*", router.handle_wildcard) 
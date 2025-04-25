#!/usr/bin/env python3
"""
NoteController - Maps OSC note messages to the OSCRouter.
"""
from pythonosc.dispatcher import Dispatcher
from lib.osc_bridge.router import OSCRouter
from . import register_controller

@register_controller
class NoteController:
    """
    Registers handlers for note_on and note_off messages.
    """
    def __init__(self, router: OSCRouter, dispatcher: Dispatcher) -> None:
        # Register note handlers with the dispatcher
        dispatcher.map("/router/note_on", router.handle_note_on)
        dispatcher.map("/router/note_off", router.handle_note_off)
        
        print("NoteController registered OSC handlers for note_on and note_off") 
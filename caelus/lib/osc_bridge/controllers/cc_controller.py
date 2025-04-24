"""
CCController - Maps OSC CC messages to OSCRouter.handle_cc
"""
from pythonosc.dispatcher import Dispatcher
from lib.osc_bridge.router import OSCRouter
from . import register_controller

@register_controller
class CCController:
    """
    Registers handler for MIDI CC messages.
    """
    def __init__(self, router: OSCRouter, dispatcher: Dispatcher) -> None:
        dispatcher.map("/router/cc", router.handle_cc) 
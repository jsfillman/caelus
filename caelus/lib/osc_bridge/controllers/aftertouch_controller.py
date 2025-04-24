"""
AftertouchController - Maps OSC aftertouch messages to the OSCRouter.
"""
from pythonosc.dispatcher import Dispatcher
from lib.osc_bridge.router import OSCRouter
from . import register_controller

@register_controller
class AftertouchController:
    """
    Registers handlers for channel and polyphonic aftertouch.
    """
    def __init__(self, router: OSCRouter, dispatcher: Dispatcher) -> None:
        dispatcher.map("/router/aftertouch", router.handle_aftertouch)
        dispatcher.map("/router/poly_aftertouch", router.handle_poly_aftertouch) 
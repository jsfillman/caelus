"""
PitchBendController - Maps OSC pitch bend messages to the OSCRouter.
"""
from pythonosc.dispatcher import Dispatcher
from lib.osc_bridge.router import OSCRouter
from . import register_controller

@register_controller
class PitchBendController:
    """
    Registers handler for OSC pitch bend messages.
    """
    def __init__(self, router: OSCRouter, dispatcher: Dispatcher) -> None:
        dispatcher.map("/router/pitch_bend", router.handle_pitch_bend) 
"""
RegisterUIController - Maps OSC register UI messages to OSCRouter.handle_register_ui.
"""
from pythonosc.dispatcher import Dispatcher
from lib.osc_bridge.router import OSCRouter
from . import register_controller

@register_controller
class RegisterUIController:
    """
    Registers handler for OSC UI registration endpoint.
    """
    def __init__(self, router: OSCRouter, dispatcher: Dispatcher) -> None:
        dispatcher.map("/router/register_ui", router.handle_register_ui) 
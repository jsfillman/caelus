"""
ParamController - Maps OSC parameter messages to OSCRouter handlers.
"""
from pythonosc.dispatcher import Dispatcher
from lib.osc_bridge.router import OSCRouter
from . import register_controller

@register_controller
class ParamController:
    """
    Registers handlers for global and per-parameter messages.
    """
    def __init__(self, router: OSCRouter, dispatcher: Dispatcher) -> None:
        # Handle setting a patch parameter across all voices
        dispatcher.map("/router/param", router.handle_param_all_voices)
        # Direct parameter endpoints
        for path in ["/cutoff", "/resonance", "/gain", "/attack", "/release"]:
            dispatcher.map(path, router.forward_param_to_voices) 
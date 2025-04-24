"""
VarController - Maps OSC variable endpoints to OSCRouter variable get/set handlers.
"""
from pythonosc.dispatcher import Dispatcher
from lib.osc_bridge.router import OSCRouter
from . import register_controller

@register_controller
class VarController:
    """
    Registers handlers for /router/set, /router/get, and direct variable endpoints.
    """
    def __init__(self, router: OSCRouter, dispatcher: Dispatcher) -> None:
        dispatcher.map("/router/set", router.handle_set_variable)
        dispatcher.map("/router/get", router.handle_get_variable)
        dispatcher.map("/router/default_cutoff", router.handle_default_cutoff)
        dispatcher.map("/router/synth_name", router.handle_synth_name)
        dispatcher.map("/router/synth_host", router.handle_synth_host) 
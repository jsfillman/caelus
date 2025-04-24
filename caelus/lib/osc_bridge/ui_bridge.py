"""
UIBridge - Manages bidirectional communication with UI clients via OSC.
"""
from typing import Optional, Any
from pythonosc import udp_client
from lib.common.utils import LOG

class UIBridge:
    """
    Manages bidirectional communication with UI clients via OSC.
    
    Handles:
    1. Sending updates to UIs (outbound: params, status, etc.)
    2. Receiving commands from UIs (inbound: UI registration in OSCRouter)
    """
    def __init__(self) -> None:
        """Initialize the bidirectional UI bridge."""
        self.ui_host: Optional[str] = None
        self.ui_port: Optional[int] = None
        self.ui_client: Optional[udp_client.SimpleUDPClient] = None

    def setup_client(self, host: str, port: int) -> bool:
        """
        Set up OSC client for sending messages to the UI.

        Args:
            host: UI host address
            port: UI port number

        Returns:
            True if setup was successful
        """
        try:
            port = int(port)
            self.ui_host = host
            self.ui_port = port
            self.ui_client = udp_client.SimpleUDPClient(host, port)
            LOG.info(f"Set up UI feedback to {host}:{port}")
            self.send_status("info", "Connected to OSC router")
            return True
        except Exception as e:
            LOG.error(f"Error setting up UI client: {e}")
            return False

    def send_status(self, status_type: str, message: str) -> bool:
        """
        Send status message to UI.

        Args:
            status_type: Type of status (info, warning, error)
            message: Status message

        Returns:
            True if message was sent successfully
        """
        if self.ui_client:
            try:
                self.ui_client.send_message("/ui/status", [status_type, message])
                LOG.debug(f"Sent UI status: {status_type} - {message}")
                return True
            except Exception as e:
                LOG.error(f"Error sending UI status: {e}")
        return False

    def send_param(self, param_name: str, value: Any) -> bool:
        """
        Send parameter update to UI.

        Args:
            param_name: Parameter name
            value: Parameter value

        Returns:
            True if message was sent successfully
        """
        if self.ui_client:
            try:
                self.ui_client.send_message("/ui/param", [param_name, value])
                LOG.debug(f"Sent UI param: {param_name} = {value}")
                return True
            except Exception as e:
                LOG.error(f"Error sending UI param: {e}")
        return False 
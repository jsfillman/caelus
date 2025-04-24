#!/usr/bin/env python3
"""
Test script for OSC messaging functionality.

This script tests sending an OSC message using the helpers.send_osc function.
"""

import sys
import logging
from pythonosc.udp_client import SimpleUDPClient
from lib.midi_osc.helpers import send_osc

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Run a simple test of the OSC messaging functionality."""
    # Create a test OSC client
    try:
        client = SimpleUDPClient("127.0.0.1", 9000)
        logger.info("Created OSC client")
        
        # Test sending a message through the helper
        result = send_osc(client, "/test", [1, 2, 3])
        logger.info(f"Message sent: {result}")
        
        # Try sending a message directly
        client.send_message("/test_direct", [4, 5, 6])
        logger.info("Direct message sent")
        
        return 0
    except Exception as e:
        logger.error(f"Error in OSC test: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 
#!/usr/bin/env python3
"""
Test OSC Router Fix

This script tests if the OSC router fix is working correctly.
It creates a simple router and tests voice allocation.
"""
import sys
import os
import time
import logging

# Add parent directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Set up detailed logging
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
root_logger.addHandler(handler)

# Our specific logger
LOG = logging.getLogger('test_router_fix')

# Import router
from lib.osc_bridge.router import OSCRouter
from pythonosc import udp_client

def main():
    """Test the router fix"""
    # Create router with default voices
    router = OSCRouter()
    
    # Create default voices
    router.create_default_voices(num_voices=1, start_port=5510)
    
    # Start router in background
    router.start_in_background()
    
    # Wait for router to start
    time.sleep(0.5)
    
    # Print information about router voices
    LOG.info("------ ROUTER VOICE INFORMATION ------")
    for i, voice in enumerate(router.voice_manager.voices):
        LOG.info(f"Voice {i}: id={voice.id}, port={voice.port}, host={voice.host}, synth_name={voice.synth_name}")
    LOG.info("-" * 40)
    
    # Create client to send messages to router
    client = udp_client.SimpleUDPClient('127.0.0.1', 9000)
    
    # Send a test note
    LOG.info("Sending test note_on...")
    client.send_message("/router/note_on", [60, 0.8])
    LOG.info("Note on message sent to router, should allocate a voice and send OSC to synth")
    
    # Wait a bit
    time.sleep(1)
    
    # Send a different note while the first is still active
    LOG.info("Sending second note_on for testing voice allocation...")
    client.send_message("/router/note_on", [64, 0.7])  # E note
    LOG.info("Second note should allocate another voice or steal one if none available")
    
    # Wait a bit
    time.sleep(1)
    
    # Send note offs
    LOG.info("Sending note_off for first note...")
    client.send_message("/router/note_off", [60])
    
    time.sleep(0.5)
    
    LOG.info("Sending note_off for second note...")
    client.send_message("/router/note_off", [64])
    
    # Wait a bit
    time.sleep(0.5)
    
    # Test completed
    LOG.info("Test completed. Check the logs for voice allocation messages.")
    LOG.info("If the test was successful, you should see messages about allocating a voice and sending OSC.")
    LOG.info("The OSC paths should be properly formatted with a slash between synth name and parameter.")
    
    # Direct test of voice communication
    LOG.info("\n------ DIRECT VOICE COMMUNICATION TEST ------")
    for i, voice in enumerate(router.voice_manager.voices):
        LOG.info(f"Testing direct communication with voice {i}...")
        # Create a mock client to save the real one
        original_client = voice.client
        
        # Record sent messages
        sent_messages = []
        
        # Create a mock client
        class MockClient:
            def send_message(self, path, value):
                sent_messages.append((path, value))
                LOG.info(f"MOCK OSC: Sent {path} = {value}")
                return True
        
        # Replace the client
        voice.client = MockClient()
        
        # Send test messages
        voice.send_osc("/test", 1.0)
        voice.note_on(60, 0.8)
        voice.note_off()
        
        # Log results
        LOG.info(f"Sent {len(sent_messages)} messages to voice {i}")
        for path, value in sent_messages:
            LOG.info(f"  - {path} = {value}")
        
        # Restore original client
        voice.client = original_client
    
    LOG.info("-" * 40)
    
    # Stop router
    router.running = False
    
    return 0

if __name__ == '__main__':
    sys.exit(main())

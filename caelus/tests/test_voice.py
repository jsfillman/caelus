#!/usr/bin/env python3
"""
Unit tests for Voice class

These tests verify that the Voice class correctly formats and sends OSC messages.
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import logging

# Add parent directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
LOG = logging.getLogger('test_voice')

# Import Voice class
from lib.osc_bridge.voice import Voice

class MockUDPClient:
    """Mock UDP client for testing"""
    
    def __init__(self, host, port):
        """Initialize with host and port"""
        self.host = host
        self.port = port
        self.messages = []
    
    def send_message(self, address, value):
        """Record message instead of sending"""
        self.messages.append((address, value))
        return True

class TestVoice(unittest.TestCase):
    """Tests for Voice class"""
    
    def setUp(self):
        """Set up test environment"""
        # Create a mock UDP client
        self.mock_client = MockUDPClient('127.0.0.1', 5001)
        
        # Create a Voice instance with the mock client
        self.voice = Voice(1, 5001, synth_name='test_synth')
        
        # Replace the client with our mock
        self.voice.client = self.mock_client
    
    def test_note_on(self):
        """Test note_on method"""
        # Call note_on
        self.voice.note_on(60, 0.8)
        
        # Check that the right messages were sent
        messages = self.mock_client.messages
        
        # Extract message addresses
        addresses = [msg[0] for msg in messages]
        
        # Verify correct format with synth name
        expected_prefix = '/test_synth/'
        for addr in addresses:
            self.assertTrue(addr.startswith(expected_prefix), 
                          f"Message address {addr} doesn't start with {expected_prefix}")
        
        # Check for the three required messages
        self.assertIn('/test_synth/freq', addresses)
        self.assertIn('/test_synth/gain', addresses)
        self.assertIn('/test_synth/gate', addresses)
        
        # Print messages for debugging
        LOG.info("Messages sent in note_on:")
        for addr, value in messages:
            LOG.info(f"  {addr} = {value}")
    
    def test_send_osc_formatting(self):
        """Test that send_osc correctly formats OSC paths"""
        # Test with leading slash
        self.voice.send_osc("/param", 1.0)
        
        # Test without leading slash
        self.voice.send_osc("param2", 2.0)
        
        # Check messages
        messages = self.mock_client.messages
        
        # Should have the format /synth_name/param
        expected_messages = [
            ('/test_synth/param', 1.0),
            ('/test_synth/param2', 2.0)
        ]
        
        for expected in expected_messages:
            self.assertIn(expected, messages, f"Message {expected} not found in sent messages")
        
        # Print messages for debugging
        LOG.info("Messages sent in send_osc test:")
        for addr, value in messages:
            LOG.info(f"  {addr} = {value}")
    
    def test_different_synth_names(self):
        """Test with different synth names"""
        # Create voices with different synth names
        voice1 = Voice(1, 5001, synth_name='synth1')
        voice1.client = MockUDPClient('127.0.0.1', 5001)
        
        voice2 = Voice(2, 5002, synth_name='synth2')
        voice2.client = MockUDPClient('127.0.0.1', 5002)
        
        # Send same message to both
        voice1.send_osc("/param", 1.0)
        voice2.send_osc("/param", 1.0)
        
        # Check that they used different synth names
        self.assertEqual(voice1.client.messages[0][0], '/synth1/param')
        self.assertEqual(voice2.client.messages[0][0], '/synth2/param')

if __name__ == '__main__':
    unittest.main()
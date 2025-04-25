#!/usr/bin/env python3
"""
Unit tests for OSC routing

These tests verify that the OSC router correctly forwards messages to the synth.
"""

import sys
import os
import unittest
import time
import tempfile
import yaml
import logging
import threading
from unittest.mock import MagicMock, patch
from typing import Dict, List, Any

# Add parent directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Set up logging to capture debug info
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
LOG = logging.getLogger('test_osc_routing')

# Import OSC router
from lib.osc_bridge.router import OSCRouter
from lib.osc_bridge.voice import Voice

class MockOSCClient:
    """Mock OSC client that records sent messages"""
    
    def __init__(self):
        """Initialize with empty message log"""
        self.messages = []
    
    def send_message(self, address, value):
        """Record the message instead of sending it"""
        self.messages.append((address, value))
        LOG.debug(f"Mock client received message: {address} = {value}")
        return True

class TestOSCRouting(unittest.TestCase):
    """Tests for OSC routing functionality"""
    
    def setUp(self):
        """Set up test environment"""
        # Create a test configuration file
        self.config_file = self._create_test_config()
        
        # Create OSC router with test config
        self.router = OSCRouter(self.config_file, router_port=9876)
        
        # Replace Voice send_osc with mock version
        self.original_send_osc = Voice.send_osc
        Voice.send_osc = self._mock_send_osc
        
        # Create message log for tracking
        self.message_log = []
        
        # Start router in background
        self.router_thread = threading.Thread(target=self._run_router)
        self.router_thread.daemon = True
        self.router_thread.start()
        
        # Wait for router to start
        time.sleep(0.5)
    
    def tearDown(self):
        """Clean up after test"""
        # Stop router
        if hasattr(self, 'router'):
            self.router.running = False
            time.sleep(0.5)
        
        # Restore original send_osc
        Voice.send_osc = self.original_send_osc
        
        # Remove test config file
        if hasattr(self, 'config_file') and os.path.exists(self.config_file):
            os.unlink(self.config_file)
    
    def _mock_send_osc(self, self_voice, path, value):
        """Mock version of Voice.send_osc that records messages"""
        # Record the message
        self.message_log.append({
            'voice_id': self_voice.id,
            'port': self_voice.port,
            'path': path,
            'value': value,
            'synth_name': self_voice.synth_name
        })
        
        # Log the message
        LOG.debug(f"Mock send_osc: voice={self_voice.id}, port={self_voice.port}, path={path}, value={value}")
        
        return True
    
    def _run_router(self):
        """Run the router in a separate thread"""
        try:
            self.router.running = True
            self.router._run_in_thread()
        except Exception as e:
            LOG.error(f"Error in router thread: {e}")
    
    def _create_test_config(self):
        """Create a test configuration file"""
        config = {
            'settings': {
                'synth_name': 'test_synth',
                'synth_host': '127.0.0.1',
                'router_port': 9876
            },
            'voices': [
                {
                    'id': 'voice1',
                    'port': 5001,
                    'host': '127.0.0.1'
                }
            ]
        }
        
        # Write to temp file
        fd, path = tempfile.mkstemp(suffix='.yaml')
        with os.fdopen(fd, 'w') as f:
            yaml.dump(config, f)
        
        return path
    
    def _create_test_client(self):
        """Create a test OSC client to send messages to the router"""
        from pythonosc import udp_client
        return udp_client.SimpleUDPClient('127.0.0.1', 9876)
    
    def _reset_message_log(self):
        """Clear the message log"""
        self.message_log = []
    
    def _find_messages(self, path_contains=None, value=None):
        """Find messages in the log that match criteria"""
        results = []
        
        for msg in self.message_log:
            path_match = True
            value_match = True
            
            if path_contains is not None:
                path_match = path_contains in str(msg['path'])
            
            if value is not None:
                value_match = msg['value'] == value
            
            if path_match and value_match:
                results.append(msg)
        
        return results
    
    def test_note_on_routing(self):
        """Test that note_on messages are routed correctly"""
        # Reset message log
        self._reset_message_log()
        
        # Create client
        client = self._create_test_client()
        
        # Send note_on message
        client.send_message("/router/note_on", [60, 0.8])
        
        # Wait for processing
        time.sleep(0.5)
        
        # Verify that the required messages were sent
        freq_messages = self._find_messages(path_contains="freq")
        self.assertTrue(len(freq_messages) > 0, "No frequency messages were sent")
        
        gain_messages = self._find_messages(path_contains="gain")
        self.assertTrue(len(gain_messages) > 0, "No gain messages were sent")
        
        gate_messages = self._find_messages(path_contains="gate", value=1)
        self.assertTrue(len(gate_messages) > 0, "No gate on messages were sent")
        
        # Check full message pattern
        LOG.info("Note On Message Log:")
        for msg in self.message_log:
            LOG.info(f"  Voice {msg['voice_id']}: {msg['path']} = {msg['value']}")
            
        self.assertGreaterEqual(len(self.message_log), 3, "Not enough messages were sent for note_on")
    
    def test_note_off_routing(self):
        """Test that note_off messages are routed correctly"""
        # First send a note_on to set up a voice allocation
        client = self._create_test_client()
        client.send_message("/router/note_on", [60, 0.8])
        time.sleep(0.5)
        
        # Reset message log
        self._reset_message_log()
        
        # Send note_off
        client.send_message("/router/note_off", [60])
        
        # Wait for processing
        time.sleep(0.5)
        
        # Verify that gate off was sent
        gate_messages = self._find_messages(path_contains="gate", value=0)
        self.assertTrue(len(gate_messages) > 0, "No gate off messages were sent")
        
        LOG.info("Note Off Message Log:")
        for msg in self.message_log:
            LOG.info(f"  Voice {msg['voice_id']}: {msg['path']} = {msg['value']}")
            
        self.assertGreaterEqual(len(self.message_log), 1, "Not enough messages were sent for note_off")
    
    def test_cc_routing(self):
        """Test that CC messages are routed correctly"""
        # Reset message log
        self._reset_message_log()
        
        # Create client
        client = self._create_test_client()
        
        # Send CC message
        client.send_message("/router/cc", [1, 64])  # Mod wheel at midpoint
        
        # Wait for processing
        time.sleep(0.5)
        
        # Verify that relevant messages were sent
        # This will depend on your implementation, but for mod wheel
        # typically cutoff or cc1 messages would be sent
        mod_messages = self._find_messages(path_contains="cc1") + self._find_messages(path_contains="cutoff")
        
        LOG.info("CC Message Log:")
        for msg in self.message_log:
            LOG.info(f"  Voice {msg['voice_id']}: {msg['path']} = {msg['value']}")
        
        # The test might need adjustment depending on your exact implementation
        self.assertGreaterEqual(len(self.message_log), 1, "No messages were sent for CC")

if __name__ == '__main__':
    unittest.main()
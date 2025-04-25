"""
BankLoader - Orchestrates loading of synth banks, spawning OSC router and synth processes, and UI registration.
"""
import os
import sys
import time
import socket
import yaml
from typing import Dict, Any

from lib.core.bank_manager import BankManager
from lib.core.synth_process_manager import SynthProcessManager
from pythonosc import udp_client
from lib.midi_osc.helpers import send_osc
from lib.core.utils import LOG

class BankLoader:
    """
    Handles loading a synth bank: stops existing processes, launches router,
    checks remote synth connections, starts local synths, and registers UI.
    """
    def __init__(
        self,
        presets_dir: str,
        osc_ip: str,
        osc_port: int,
        router_name: str,
        ui_osc_port: int
    ) -> None:
        self.bank_manager = BankManager(presets_dir)
        self.process_manager = SynthProcessManager()
        self.osc_ip = osc_ip
        self.osc_port = osc_port
        self.router_name = router_name
        self.ui_osc_port = ui_osc_port
        self.osc_client = udp_client.SimpleUDPClient(osc_ip, osc_port)

    def load_bank(self, bank_name: str) -> Dict[str, int]:
        """
        Load a synth bank: kill existing, load bank info, test remotes, start router,
        launch local synths, register UI, and optionally launch bank-specific UI.

        Returns:
            Dict with counts: {'local': int, 'remote': int}

        Raises:
            Exception on failure
        """
        # Stop any running processes
        LOG.info(f"Stopping existing synth and router processes")
        self.process_manager.kill_all()

        # Load bank configuration (voices.yaml and synth binary path)
        info = self.bank_manager.load_bank(bank_name)
        bank_dir = info['bank_dir']
        voices_cfg = info['config']
        synth_path = info['synth_file']

        # Host settings
        default_host = voices_cfg.get('settings', {}).get('synth_host', '127.0.0.1')

        # Step 1: Test remote synth connectivity
        remote_count = 0
        for voice in voices_cfg.get('voices', []):
            host = voice.get('host', default_host)
            port = voice.get('port')
            vid = voice.get('id')
            if host not in ('127.0.0.1', 'localhost'):
                LOG.info(f"Testing remote synth {vid} at {host}:{port}")
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(2)
                    if sock.connect_ex((host, port)) == 0:
                        remote_count += 1
                        LOG.info(f"Remote synth {vid} reachable")
                    else:
                        LOG.warning(f"Remote synth {vid} not reachable")
                    sock.close()
                except Exception as e:
                    LOG.error(f"Error testing {host}:{port}: {e}")

        # Step 2: Launch OSC router with UI feedback
        router_cmd = [
            sys.executable,
            "-m", "lib.osc_bridge.main",
            "-c", os.path.join(bank_dir, 'voices.yaml'),
            "-p", str(self.osc_port),
            "--ui-host", self.osc_ip,
            "--ui-port", str(self.ui_osc_port),
            "--background"  # Run in background mode to keep process alive
        ]
        LOG.info(f"Starting OSC router: {' '.join(router_cmd)}")
        router_proc = self.process_manager.spawn_router(router_cmd)
        if not router_proc:
            raise RuntimeError("Failed to spawn OSC router process")

        # Give router time to initialize
        time.sleep(2)

        # Test OSC router
        try:
            send_osc(self.osc_client, f"/{self.router_name}/all_notes_off", [])
            LOG.info("OSC router test passed")
        except Exception as e:
            LOG.warning(f"OSC router test failed: {e}")

        # Step 3: Launch local synth processes
        local_count = 0
        for voice in voices_cfg.get('voices', []):
            host = voice.get('host', default_host)
            port = voice.get('port')
            vid = voice.get('id')
            if host in ('127.0.0.1', 'localhost'):
                cmd = [synth_path, '-port', str(port)]
                LOG.info(f"Launching local synth {vid} on port {port}")
                proc = self.process_manager.spawn_synth(cmd, f"synth_{vid}")
                if proc:
                    local_count += 1
                    time.sleep(0.5)

        # Step 4: Register this GUI as UI client with router
        LOG.info(f"Registering UI client at {self.osc_ip}:{self.ui_osc_port}")
        send_osc(self.osc_client, f"/{self.router_name}/register_ui", [self.osc_ip, self.ui_osc_port])

        # Optionally launch a separate UI for the bank if present
        ui_script = os.path.join(bank_dir, 'ui.py')
        if os.path.exists(ui_script):
            LOG.info(f"Found bank-specific UI: {ui_script} (embedded in main application)")
            # Note: We're not launching a separate process for the UI since it's already
            # embedded in the main application. This prevents duplicate UIs and potential crashes.
            #self.process_manager.spawn_synth([sys.executable, ui_script], f"UI_{bank_name}")

        LOG.info(f"Bank '{bank_name}' loaded: {local_count} local, {remote_count} remote synths")
        return {'local': local_count, 'remote': remote_count} 
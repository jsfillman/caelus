"""
ConfigLoader - Loads and parses configuration for the OSC Router.
"""
import json
import yaml
from typing import Any, Dict, List, Tuple

from lib.common.utils import LOG, DEFAULT_SYNTH_HOST, DEFAULT_SYNTH_NAME
from lib.osc_bridge.voice import Voice

class ConfigLoader:
    """
    Loads and parses configuration for the OSC Router.
    """
    @staticmethod
    def load_config(config_file: str) -> Tuple[Dict[str, Any], List[Voice]]:
        """
        Load configuration from YAML or JSON file.

        Args:
            config_file: Path to configuration file.

        Returns:
            Tuple of settings dict and list of Voice instances.

        Raises:
            Exception if loading or parsing the config file fails.
        """
        try:
            with open(config_file, 'r') as f:
                if config_file.endswith(('.yaml', '.yml')):
                    config = yaml.safe_load(f)
                else:
                    config = json.load(f)

            settings: Dict[str, Any] = {
                'synth_name': DEFAULT_SYNTH_NAME,
                'synth_host': DEFAULT_SYNTH_HOST,
            }

            if 'settings' in config:
                if 'synth_host' in config['settings']:
                    settings['synth_host'] = config['settings']['synth_host']
                if 'synth_name' in config['settings']:
                    settings['synth_name'] = config['settings']['synth_name']

            voices: List[Voice] = []
            if 'voices' in config:
                for voice_config in config['voices']:
                    voice_id = voice_config['id']
                    port = voice_config['port']
                    host = voice_config.get('host', settings['synth_host'])
                    voice = Voice(
                        voice_id,
                        port,
                        host=host,
                        synth_name=settings['synth_name']
                    )
                    voices.append(voice)

            return settings, voices
        except Exception as e:
            LOG.error(f"Error loading config: {e}")
            raise 
#!/usr/bin/env python3
"""
Check audio system status for Caelus.
This script verifies:
1. JACK server status
2. Audio device availability
3. FAUST compiler availability
"""

import os
import sys
import subprocess
import shutil
from typing import Dict, List, Tuple

def run_command(cmd: List[str]) -> Tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr"""
    try:
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        stdout, stderr = process.communicate()
        return process.returncode, stdout, stderr
    except Exception as e:
        return -1, "", str(e)

def check_command_exists(cmd: str) -> bool:
    """Check if a command exists in the system path"""
    return shutil.which(cmd) is not None

def check_jack_status() -> Dict:
    """Check JACK audio server status"""
    results = {
        "installed": False,
        "running": False,
        "version": None,
        "error": None,
        "devices": [],
        "sample_rate": None
    }
    
    # Check if jackd is installed
    if not check_command_exists("jackd"):
        results["error"] = "JACK is not installed or not in PATH"
        return results
    
    results["installed"] = True
    
    # Get JACK version
    code, stdout, stderr = run_command(["jackd", "--version"])
    if code == 0:
        results["version"] = stdout.strip()
    
    # Check if JACK server is running
    code, stdout, stderr = run_command(["jack_wait", "-c", "-t", "1"])
    results["running"] = (code == 0)
    
    if results["running"]:
        # Get JACK server status (sample rate, etc)
        code, stdout, stderr = run_command(["jack_lsp", "-s"])
        if code == 0:
            results["devices"] = [line.strip() for line in stdout.splitlines() if line.strip()]
            
        # Try to get sample rate
        code, stdout, stderr = run_command(["jack_samplerate"])
        if code == 0:
            try:
                results["sample_rate"] = int(stdout.strip())
            except ValueError:
                pass
    
    return results

def check_audio_devices() -> Dict:
    """Check available audio devices"""
    results = {
        "coreaudio": False,
        "portaudio": False,
        "devices": []
    }
    
    # Check CoreAudio (macOS)
    if sys.platform == "darwin":
        results["coreaudio"] = True
        # Try to get audio devices using system_profiler
        code, stdout, stderr = run_command(["system_profiler", "SPAudioDataType"])
        if code == 0:
            # Parse the output to extract device names
            devices = []
            in_audio_section = False
            for line in stdout.splitlines():
                if "Audio:" in line:
                    in_audio_section = True
                    continue
                
                if in_audio_section and ":" in line and not "Manufacturer" in line:
                    device_name = line.split(":", 1)[0].strip()
                    if device_name and not device_name.startswith(" "):
                        devices.append(device_name)
            
            results["devices"] = devices
    
    # Check PortAudio (cross-platform)
    try:
        import pyaudio
        results["portaudio"] = True
        
        # List devices
        p = pyaudio.PyAudio()
        device_count = p.get_device_count()
        
        for i in range(device_count):
            device_info = p.get_device_info_by_index(i)
            device_name = device_info.get("name")
            if device_name and device_name not in results["devices"]:
                results["devices"].append(device_name)
        
        p.terminate()
    except ImportError:
        pass
    
    return results

def check_faust_compiler() -> Dict:
    """Check Faust compiler status"""
    results = {
        "installed": False,
        "version": None,
        "error": None
    }
    
    # Check if faust is installed
    if not check_command_exists("faust"):
        results["error"] = "Faust compiler is not installed or not in PATH"
        return results
    
    results["installed"] = True
    
    # Get Faust version
    code, stdout, stderr = run_command(["faust", "-v"])
    if code == 0:
        results["version"] = stdout.strip()
    else:
        results["error"] = f"Failed to get Faust version: {stderr}"
    
    return results

def print_summary(jack_status, audio_devices, faust_status):
    """Print a summary of the audio system status"""
    print("\n=== Caelus Audio System Check ===\n")
    
    # JACK status
    print("JACK Audio Server:")
    print(f"  Installed: {'Yes' if jack_status['installed'] else 'No'}")
    if jack_status["installed"]:
        print(f"  Version: {jack_status['version'] or 'Unknown'}")
        print(f"  Running: {'Yes' if jack_status['running'] else 'No'}")
        
        if jack_status["running"]:
            print(f"  Sample Rate: {jack_status['sample_rate'] or 'Unknown'}")
            if jack_status["devices"]:
                print("  Connected Ports:")
                for device in jack_status["devices"]:
                    print(f"    - {device}")
        else:
            print("  Server not running - use 'jackd -d coreaudio' to start")
    else:
        print(f"  Error: {jack_status['error']}")
    
    # Audio devices
    print("\nAudio Devices:")
    print(f"  CoreAudio (macOS): {'Available' if audio_devices['coreaudio'] else 'Not available'}")
    print(f"  PortAudio: {'Available' if audio_devices['portaudio'] else 'Not available'}")
    
    if audio_devices["devices"]:
        print("  Detected Devices:")
        for device in audio_devices["devices"]:
            print(f"    - {device}")
    else:
        print("  No audio devices detected")
    
    # Faust status
    print("\nFaust Compiler:")
    print(f"  Installed: {'Yes' if faust_status['installed'] else 'No'}")
    if faust_status["installed"]:
        print(f"  Version: {faust_status['version'] or 'Unknown'}")
    else:
        print(f"  Error: {faust_status['error']}")
    
    # Recommendations
    print("\nRecommendations:")
    if not jack_status["installed"]:
        print("  - Install JACK audio server (brew install jack or visit jackaudio.org)")
    elif not jack_status["running"]:
        print("  - Start JACK server before running Caelus:")
        print("    jackd -d coreaudio")
    
    if not faust_status["installed"]:
        print("  - Install Faust compiler (brew install faust or visit faust.grame.fr)")
    
    print("\n=== End of Audio System Check ===\n")

def main():
    """Main function"""
    jack_status = check_jack_status()
    audio_devices = check_audio_devices()
    faust_status = check_faust_compiler()
    
    print_summary(jack_status, audio_devices, faust_status)
    
    # Return error code if problems were found
    if (not jack_status["installed"] or 
        not jack_status["running"] or 
        not faust_status["installed"]):
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
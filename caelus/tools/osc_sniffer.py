#!/usr/bin/env python3
"""
OSC UDP Traffic Sniffer

This script captures and displays UDP traffic on specified ports without
interfering with existing connections. It works by creating a raw socket
and analyzing UDP packets to detect OSC messages.

Note: This requires root privileges to run due to the use of raw sockets.
Run with: sudo python3 osc_sniffer.py
"""

import socket
import sys
import struct
import argparse
import time
import signal
import binascii
from datetime import datetime

class OSCSniffer:
    """Sniff and decode OSC packets from UDP traffic"""
    
    def __init__(self, ports=None, interface='lo0'):
        """Initialize with ports to monitor"""
        self.ports = ports or []
        self.interface = interface
        self.raw_socket = None
        self.running = False
        self.stats = {
            'total_packets': 0,
            'osc_packets': 0,
            'start_time': None
        }
    
    def start_sniffing(self):
        """Start sniffing for OSC packets"""
        try:
            # Create a raw socket
            self.raw_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_UDP)
            
            # Set socket options if needed
            # self.raw_socket.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
            
            # Record start time
            self.stats['start_time'] = datetime.now()
            self.running = True
            
            print(f"Sniffing for OSC traffic on ports: {', '.join(map(str, self.ports))}")
            print("Press Ctrl+C to stop.")
            
            # Start sniffing
            while self.running:
                # Receive a packet (65535 is max UDP packet size)
                packet, addr = self.raw_socket.recvfrom(65535)
                self.stats['total_packets'] += 1
                
                # Parse the packet
                self._parse_packet(packet, addr)
                
        except socket.error as e:
            print(f"Socket error: {e}")
            if e.errno == 1:
                print("Permission denied: You need to run this script with sudo.")
            return False
        except Exception as e:
            print(f"Error: {e}")
            return False
            
        return True
    
    def _parse_packet(self, packet, addr):
        """Parse an IP/UDP packet and extract OSC data"""
        try:
            # Parse IP header (first 20 bytes)
            ip_header = packet[0:20]
            iph = struct.unpack('!BBHHHBBH4s4s', ip_header)
            
            # Extract header length and protocol
            ihl = (iph[0] & 0xF) * 4
            protocol = iph[6]
            
            # Check if UDP (protocol 17)
            if protocol != 17:
                return
            
            # Parse UDP header
            udp_header_start = ihl
            udp_header_end = udp_header_start + 8
            udp_header = packet[udp_header_start:udp_header_end]
            
            # Unpack UDP header
            udph = struct.unpack('!HHHH', udp_header)
            source_port = udph[0]
            dest_port = udph[1]
            length = udph[2]
            
            # Check if we care about this port
            if self.ports and dest_port not in self.ports:
                return
            
            # Extract OSC data
            osc_data_start = udp_header_end
            osc_data = packet[osc_data_start:]
            
            # Check if this looks like an OSC message (starts with '/')
            if osc_data and osc_data[0] == 47:  # '/' is ASCII 47
                self.stats['osc_packets'] += 1
                
                # Try to decode the OSC message
                osc_address, args = self._decode_osc(osc_data)
                
                # Print the decoded message
                timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                direction = f"{addr[0]}:{source_port} → {addr[0]}:{dest_port}"
                print(f"[{timestamp}] {direction} | {osc_address} {args}")
                
        except Exception as e:
            print(f"Error parsing packet: {e}")
    
    def _decode_osc(self, data):
        """Decode an OSC message from binary data"""
        try:
            # Find the end of the address string (null-terminated)
            end_address = 0
            while end_address < len(data) and data[end_address] != 0:
                end_address += 1
            
            # Extract address
            osc_address = data[:end_address].decode('utf-8')
            
            # Skip null padding (address is padded to multiple of 4 bytes)
            type_tag_start = ((end_address + 4) // 4) * 4
            
            # Process type tag if present
            if type_tag_start < len(data) and data[type_tag_start] == 44:  # ',' is ASCII 44
                # Find the end of the type tag string
                end_type_tag = type_tag_start
                while end_type_tag < len(data) and data[end_type_tag] != 0:
                    end_type_tag += 1
                
                # Extract type tag
                type_tag = data[type_tag_start:end_type_tag].decode('utf-8')
                
                # Skip null padding
                args_start = ((end_type_tag + 4) // 4) * 4
                
                # Parse arguments based on type tag
                args = []
                arg_index = args_start
                
                for t in type_tag[1:]:  # Skip the initial ','
                    if t == 'i':  # Integer
                        if arg_index + 4 <= len(data):
                            val = struct.unpack('>i', data[arg_index:arg_index+4])[0]
                            args.append(val)
                            arg_index += 4
                    elif t == 'f':  # Float
                        if arg_index + 4 <= len(data):
                            val = struct.unpack('>f', data[arg_index:arg_index+4])[0]
                            args.append(val)
                            arg_index += 4
                    elif t == 's':  # String
                        end_string = arg_index
                        while end_string < len(data) and data[end_string] != 0:
                            end_string += 1
                        
                        val = data[arg_index:end_string].decode('utf-8')
                        args.append(val)
                        
                        # Skip null padding
                        arg_index = ((end_string + 4) // 4) * 4
                    else:
                        # Unknown type, just display hex
                        args.append(f"<{t}?>")
                
                return osc_address, args
            else:
                # No type tag, just display raw data
                hex_data = binascii.hexlify(data[type_tag_start:]).decode('utf-8')
                if len(hex_data) > 20:
                    hex_data = hex_data[:20] + "..."
                return osc_address, f"<raw: {hex_data}>"
                
        except Exception as e:
            # If decoding fails, return raw data as hex
            hex_data = binascii.hexlify(data).decode('utf-8')
            if len(hex_data) > 20:
                hex_data = hex_data[:20] + "..."
            return "<invalid>", f"<raw: {hex_data}>"
    
    def stop_sniffing(self):
        """Stop sniffing"""
        self.running = False
        
        if self.raw_socket:
            self.raw_socket.close()
        
        # Print summary
        duration = datetime.now() - self.stats['start_time']
        duration_secs = duration.total_seconds()
        
        print("\n=== Sniffing Summary ===")
        print(f"Duration: {duration_secs:.1f} seconds")
        print(f"Total UDP packets: {self.stats['total_packets']}")
        print(f"OSC packets detected: {self.stats['osc_packets']}")
        
        if duration_secs > 0:
            print(f"Packets per second: {self.stats['total_packets']/duration_secs:.1f}")
            print(f"OSC packets per second: {self.stats['osc_packets']/duration_secs:.1f}")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Sniff for OSC traffic on UDP ports")
    parser.add_argument("ports", nargs="+", type=int, 
                      help="UDP ports to monitor (e.g. 5510 9000)")
    parser.add_argument("-i", "--interface", type=str, default="lo0",
                      help="Network interface to listen on (default: lo0)")
    
    args = parser.parse_args()
    
    # Check if running as root
    if not hasattr(socket, 'SOL_IP'):
        socket.SOL_IP = socket.IPPROTO_IP
        
    # Create sniffer
    sniffer = OSCSniffer(args.ports, args.interface)
    
    # Set up signal handler for clean exit
    def signal_handler(sig, frame):
        print("\nStopping sniffer...")
        sniffer.stop_sniffing()
        sys.exit(0)
        
    signal.signal(signal.SIGINT, signal_handler)
    
    # Start sniffing
    sniffer.start_sniffing()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
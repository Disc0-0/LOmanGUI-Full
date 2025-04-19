#!/usr/bin/env python3
# lo_server_query.py - Last Oasis Server Query Tool
# This tool uses both Steam and Unreal Engine query protocols to get information from Last Oasis servers
# including map names, player counts, and other server information.

import sys
import os
import argparse
import socket
import logging
import json
import csv
import time
import concurrent.futures
import struct
import binascii
from typing import List, Dict, Any, Optional, Tuple, Union

try:
    import a2s
except ImportError:
    print("Required package 'python-a2s' not found.")
    print("Please install it using: pip install python-a2s")
    sys.exit(1)

# Constants
# Constants
DEFAULT_TIMEOUT = 5.0  # Default query timeout in seconds
DEFAULT_STEAM_QUERY_PORT = 27015  # Default Steam query port
DEFAULT_UNREAL_QUERY_PORT = 7777  # Default Unreal Engine query port
UNREAL_QUERY_PORT_OFFSET = 1001  # Typical offset for Unreal query port (game port + offset)
STEAM_MASTER_SERVER = ("hl2master.steampowered.com", 27011)  # Steam master server
LAST_OASIS_APP_ID = 903950  # Last Oasis Steam App ID
LOG_FILE = "lo_server_query.log"
DEFAULT_OUTPUT_FILE = "server_maps.json"

# Unreal Engine Query Constants
UNREAL_CHALLENGE_PACKET = b'\x04\x05\x06\x07'  # Initial challenge packet
UNREAL_INFO_REQUEST = b'\x00\x00\x00\x00'      # Request server info with a challenge response
UNREAL_PLAYER_REQUEST = b'\x00\x00\x00\x01'    # Request player info
UNREAL_RULES_REQUEST = b'\x00\x00\x00\x02'     # Request rules
# Set up logging
def setup_logging(verbose=False):
    log_level = logging.DEBUG if verbose else logging.INFO
    log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    root_logger.addHandler(console_handler)
    
    # File Handler
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setFormatter(log_formatter)
    root_logger.addHandler(file_handler)
    
    return root_logger

# Parse command line arguments
def parse_arguments():
    parser = argparse.ArgumentParser(description='Last Oasis Server Query Tool')
    parser.add_argument('--server', type=str, help='Specific server to query (IP:port format)')
    parser.add_argument('--servers', type=str, help='File with list of servers to query (one per line, IP:port format)')
    parser.add_argument('--output', type=str, default=DEFAULT_OUTPUT_FILE, 
                      help=f'Output file for results (default: {DEFAULT_OUTPUT_FILE})')
    parser.add_argument('--format', choices=['json', 'csv', 'txt'], default='json',
                      help='Output format (default: json)')
    parser.add_argument('--timeout', type=float, default=DEFAULT_TIMEOUT,
                      help=f'Query timeout in seconds (default: {DEFAULT_TIMEOUT})')
    parser.add_argument('--discover', action='store_true',
                      help='Attempt to discover Last Oasis servers via Steam master server')
    parser.add_argument('--verbose', action='store_true',
                      help='Enable verbose logging')
    parser.add_argument('--scan-ports', type=str, 
                      help='Scan IP address for Steam query ports (format: IP:start_port-end_port)')
    parser.add_argument('--protocol', choices=['steam', 'unreal', 'both'], default='both',
                      help='Server query protocol to use (default: both)')
    parser.add_argument('--unreal-port', type=int, default=DEFAULT_UNREAL_QUERY_PORT,
                      help=f'Default Unreal Engine query port (default: {DEFAULT_UNREAL_QUERY_PORT})')
    return parser.parse_args()

# Parse server address in format IP:port
def parse_server_address(address: str) -> Tuple[str, int]:
    parts = address.strip().split(':')
    ip = parts[0]
    port = int(parts[1]) if len(parts) > 1 else DEFAULT_STEAM_QUERY_PORT
    return (ip, port)

# Read list of servers from file
def read_server_list(filename: str) -> List[Tuple[str, int]]:
    servers = []
    try:
        with open(filename, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    servers.append(parse_server_address(line))
        logging.info(f"Loaded {len(servers)} servers from {filename}")
        return servers
    except Exception as e:
        logging.error(f"Failed to read server list: {e}")
        return []

# Send Unreal Engine query packet and receive response
def unreal_query(address: Tuple[str, int], query_type: bytes, challenge: bytes = None, timeout: float = 2.0) -> Optional[bytes]:
    """
    Send a query to an Unreal Engine server and receive the response
    
    Args:
        address: Tuple of (IP, port)
        query_type: Type of query (info, players, rules)
        challenge: Challenge response from server if needed
        timeout: Timeout in seconds
        
    Returns:
        Response bytes or None if failed
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    
    try:
        # Construct packet based on query type
        if challenge is None:
            # Initial packet to get challenge
            packet = UNREAL_CHALLENGE_PACKET
        else:
            # Query with challenge response
            packet = challenge + query_type
            
        logging.debug(f"Sending Unreal query packet to {address}: {binascii.hexlify(packet)}")
        sock.sendto(packet, address)
        
        # Receive response
        response, _ = sock.recvfrom(4096)
        logging.debug(f"Received Unreal response: {len(response)} bytes")
        return response
        
    except socket.timeout:
        logging.debug(f"Timeout querying Unreal server {address}")
        return None
    except ConnectionRefusedError:
        logging.debug(f"Connection refused by Unreal server {address}")
        return None
    except Exception as e:
        logging.debug(f"Error querying Unreal server {address}: {e}")
        return None
    finally:
        sock.close()

# Parse Unreal Engine server info response
def parse_unreal_server_info(data: bytes) -> Optional[Dict[str, Any]]:
    """
    Parse the response from an Unreal Engine server info query
    
    Args:
        data: Response data from the server
        
    Returns:
        Dictionary with server information or None if parsing failed
    """
    try:
        if not data or len(data) < 10:
            return None
            
        # Check header
        if data[0:4] != b'\x00\x00\x00\x00':
            logging.debug("Invalid Unreal info response header")
            return None
            
        # Skip header (4 bytes) and read null-terminated strings
        offset = 4
        result = {}
        
        # Read server name
        name_end = data.find(b'\x00', offset)
        if name_end == -1:
            return None
        result['server_name'] = data[offset:name_end].decode('latin-1', errors='replace')
        offset = name_end + 1
        
        # Read map name
        map_end = data.find(b'\x00', offset)
        if map_end == -1:
            return None
        result['map_name'] = data[offset:map_end].decode('latin-1', errors='replace')
        offset = map_end + 1
        
        # Read game name
        game_end = data.find(b'\x00', offset)
        if game_end == -1:
            return None
        result['game'] = data[offset:game_end].decode('latin-1', errors='replace')
        offset = game_end + 1
        
        # Try to parse remaining data - depends on game version
        try:
            # Read player count and max players
            if offset + 4 <= len(data):
                result['player_count'] = struct.unpack('!H', data[offset:offset+2])[0]
                result['max_players'] = struct.unpack('!H', data[offset+2:offset+4])[0]
                offset += 4
                
                # Try to parse additional fields if present
                if offset + 2 <= len(data):
                    result['port'] = struct.unpack('!H', data[offset:offset+2])[0]
                    offset += 2
                    
                    # Some Unreal games include server flags and other data
                    if offset + 4 <= len(data):
                        flags = data[offset]
                        result['password_protected'] = bool(flags & 1)
                        result['dedicated'] = bool(flags & 2)
        except Exception as e:
            logging.debug(f"Error parsing Unreal server details: {e}")
            # Continue anyway, we already have basic info
            
        return result
        
    except Exception as e:
        logging.debug(f"Error parsing Unreal server info response: {e}")
        return None

# Parse Unreal Engine player info response
def parse_unreal_player_info(data: bytes) -> List[Dict[str, Any]]:
    """
    Parse the response from an Unreal Engine player info query
    
    Args:
        data: Response data from the server
        
    Returns:
        List of player information dictionaries
    """
    players = []
    
    try:
        if not data or len(data) < 5:
            return players
            
        # Check header
        if data[0:4] != b'\x00\x00\x00\x01':
            return players
            
        # Skip header (4 bytes)
        offset = 4
        
        # Number of players
        num_players = data[offset]
        offset += 1
        
        # Parse each player
        for _ in range(num_players):
            player = {}
            
            # Read player name
            name_end = data.find(b'\x00', offset)
            if name_end == -1:
                break
            player['name'] = data[offset:name_end].decode('latin-1', errors='replace')
            offset = name_end + 1
            
            # Read score
            if offset + 4 <= len(data):
                player['score'] = struct.unpack('!i', data[offset:offset+4])[0]
                offset += 4
            else:
                player['score'] = 0
                break
                
            # Read ping
            if offset + 4 <= len(data):
                player['ping'] = struct.unpack('!i', data[offset:offset+4])[0]
                offset += 4
            else:
                player['ping'] = 0
                break
                
            players.append(player)
            
        return players
        
    except Exception as e:
        logging.debug(f"Error parsing Unreal player info response: {e}")
        return players

# Query an Unreal Engine server
def query_unreal_server(address: Tuple[str, int], timeout: float) -> Optional[Dict[str, Any]]:
    """
    Query an Unreal Engine server for information
    
    Args:
        address: Tuple of (IP, port)
        timeout: Timeout in seconds
        
    Returns:
        Dictionary with server information or None if query failed
    """
    ip, port = address
    server_address_str = f"{ip}:{port}"
    logging.info(f"Querying Unreal Engine server {server_address_str}")
    
    try:
        # First get the challenge response
        challenge = unreal_query(address, None, None, timeout)
        if not challenge or len(challenge) < 4:
            logging.debug(f"No challenge response from Unreal server {server_address_str}")
            return None
            
        # Now query for server info
        info_response = unreal_query(address, UNREAL_INFO_REQUEST, challenge, timeout)
        if not info_response:
            logging.debug(f"No info response from Unreal server {server_address_str}")
            return None
            
        server_info = parse_unreal_server_info(info_response)
        if not server_info:
            logging.debug(f"Could not parse Unreal server info from {server_address_str}")
            return None
            
        # Query for player info
        player_response = unreal_query(address, UNREAL_PLAYER_REQUEST, challenge, timeout)
        if player_response:
            players = parse_unreal_player_info(player_response)
        else:
            players = []
            
        # Build result
        result = {
            "address": server_address_str,
            "map": server_info.get('map_name', 'Unknown'),
            "game": server_info.get('game', 'Last Oasis'),
            "player_count": server_info.get('player_count', 0),
            "max_players": server_info.get('max_players', 0),
            "password_protected": server_info.get('password_protected', False),
            "dedicated": server_info.get('dedicated', True),
            "protocol": "unreal",
            "players": players,
            "query_time": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        logging.info(f"Successfully queried Unreal server {server_address_str}: Map '{server_info.get('map_name')}', Players: {server_info.get('player_count')}/{server_info.get('max_players')}")
        return result
        
    except Exception as e:
        logging.warning(f"Error querying Unreal server {server_address_str}: {e}")
        return None

# Query a single server for information
def query_server(address: Tuple[str, int], timeout: float) -> Optional[Dict[str, Any]]:
    ip, port = address
    server_address_str = f"{ip}:{port}"
    logging.info(f"Querying server {server_address_str}")
    
    try:
        # Get server info
        info = a2s.info(address, timeout=timeout)
        # Get player info
        try:
            players = a2s.players(address, timeout=timeout)
        except Exception as e:
            logging.warning(f"Could not get player info from {server_address_str}: {e}")
            players = []
        
        # Get rules
        try:
            rules = a2s.rules(address, timeout=timeout)
        except Exception as e:
            logging.warning(f"Could not get rules from {server_address_str}: {e}")
            rules = {}
        
        # Extract relevant information
        server_info = {
            "address": server_address_str,
            "name": info.server_name,
            "map": info.map_name,
            "game": info.game,
            "player_count": info.player_count,
            "max_players": info.max_players,
            "bot_count": info.bot_count,
            "server_type": info.server_type,
            "platform": info.platform,
            "password_protected": info.password_protected,
            "vac_enabled": info.vac_enabled,
            "version": info.version,
            "players": [
                {
                    "name": player.name,
                    "score": player.score,
                    "duration": player.duration
                } for player in players
            ],
            "rules": {key: value for key, value in rules.items()} if isinstance(rules, dict) else {},
            "query_time": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        logging.info(f"Successfully queried {server_address_str}: Map '{info.map_name}', Players: {info.player_count}/{info.max_players}")
        return server_info
    
    except socket.timeout:
        logging.warning(f"Timeout querying {server_address_str}")
        return None
    except a2s.BrokenMessageError:
        logging.warning(f"Broken message from {server_address_str}")
        return None
    except ConnectionRefusedError:
        logging.warning(f"Connection refused by {server_address_str}")
        return None
    except Exception as e:
        logging.warning(f"Error querying {server_address_str}: {e}")
        return None

# Scan ports on an IP to find Steam servers
def scan_ports(ip: str, start_port: int, end_port: int, timeout: float = 1.0) -> List[Tuple[str, int]]:
    found_servers = []
    total_ports = end_port - start_port + 1
    
    logging.info(f"Scanning {ip} for Steam servers on ports {start_port}-{end_port}...")
    
    def check_port(port):
        address = (ip, port)
        try:
            info = a2s.info(address, timeout=timeout)
            return (ip, port, info.server_name, info.map_name)
        except:
            return None
    
    # Use ThreadPoolExecutor for parallel scanning
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_port = {executor.submit(check_port, port): port for port in range(start_port, end_port + 1)}
        
        completed = 0
        for future in concurrent.futures.as_completed(future_to_port):
            completed += 1
            if completed % 100 == 0:
                logging.info(f"Scanned {completed}/{total_ports} ports...")
            
            result = future.result()
            if result:
                ip, port, name, map_name = result
                server_address = (ip, port)
                found_servers.append(server_address)
                logging.info(f"Found server at {ip}:{port} - {name} - Map: {map_name}")
    
    logging.info(f"Port scan complete. Found {len(found_servers)} servers.")
    return found_servers

# Write server info to file
def write_output(server_info_list: List[Dict[str, Any]], output_file: str, format_type: str):
    if not server_info_list:
        logging.warning("No server information to write")
        return
    
    try:
        if format_type == 'json':
            with open(output_file, 'w') as f:
                json.dump(server_info_list, f, indent=2)
            
        elif format_type == 'csv':
            with open(output_file, 'w', newline='') as f:
                fieldnames = ['address', 'name', 'map', 'player_count', 'max_players', 'version', 'query_time']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for server in server_info_list:
                    writer.writerow({
                        'address': server['address'],
                        'name': server['name'],
                        'map': server['map'],
                        'player_count': server['player_count'],
                        'max_players': server['max_players'],
                        'version': server['version'],
                        'query_time': server['query_time']
                    })
            
        elif format_type == 'txt':
            with open(output_file, 'w') as f:
                for server in server_info_list:
                    f.write(f"Server: {server['name']}\n")
                    f.write(f"Address: {server['address']}\n")
                    f.write(f"Map: {server['map']}\n")
                    f.write(f"Players: {server['player_count']}/{server['max_players']}\n")
                    f.write(f"Version: {server['version']}\n")
                    f.write(f"Query Time: {server['query_time']}\n")
                    f.write("\n")
        
        logging.info(f"Successfully wrote {len(server_info_list)} server entries to {output_file}")
    
    except Exception as e:
        logging.error(f"Failed to write output: {e}")

# Display server information in console
def display_server_info(server_info_list: List[Dict[str, Any]]):
    if not server_info_list:
        print("No servers found or all queries failed.")
        return
    
    print("\n=== Last Oasis Server Information ===")
    print(f"Found {len(server_info_list)} servers\n")
    
    for server in server_info_list:
        print(f"Server: {server['name']}")
        print(f"Address: {server['address']}")
        print(f"Map: {server['map']}")
        print(f"Players: {server['player_count']}/{server['max_players']}")
        print(f"Game: {server['game']}")
        print(f"Version: {server['version']}")
        
        if server['players']:
            print(f"Online Players ({len(server['players'])}):")
            for player in server['players']:
                if 'duration' in player:
                    play_time = f"{int(player['duration'] // 60)}:{int(player['duration'] % 60):02d}" if player['duration'] is not None else "N/A"
                    print(f"  - {player['name']} (Score: {player['score']}, Time: {play_time})")
                else:
                    print(f"  - {player['name']} (Score: {player.get('score', 'N/A')})")
        
        print("-" * 50)

# Main execution
def main():
    args = parse_arguments()
    logger = setup_logging(args.verbose)
    logger.info("Starting Last Oasis Server Query Tool")
    
    servers_to_query = []
    
    # Handle server scan if requested
    if args.scan_ports:
        try:
            scan_info = args.scan_ports.split(':')
            ip = scan_info[0]
            port_range = scan_info[1].split('-')
            start_port = int(port_range[0])
            end_port = int(port_range[1])
            
            found_servers = scan_ports(ip, start_port, end_port, args.timeout / 2)
            servers_to_query.extend(found_servers)
            
        except Exception as e:
            logger.error(f"Failed to scan ports: {e}")
            return 1
    
    # Add specific server if provided
    if args.server:
        try:
            servers_to_query.append(parse_server_address(args.server))
        except Exception as e:
            logger.error(f"Invalid server address format: {e}")
            return 1
    
    # Add servers from file if provided
    if args.servers:
        file_servers = read_server_list(args.servers)
        servers_to_query.extend(file_servers)
    
    # Discover servers via Steam master server if requested
    if args.discover:
        logger.info("Server discovery not currently supported - requires additional implementation")
        # This would require implementing the Steam master server protocol or using a library
    
    # Make sure we have servers to query
    if not servers_to_query:
        logger.error("No servers to query. Specify --server, --servers, --scan-ports, or --discover")
        return 1
    
    logger.info(f"Preparing to query {len(servers_to_query)} servers")
    
    # Query all servers (with parallel processing for better performance)
    server_info_list = []
    server_info_list = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        
        # Submit query tasks based on selected protocol
        for server in servers_to_query:
            if args.protocol in ['steam', 'both']:
                futures.append((executor.submit(query_server, server, args.timeout), server, 'steam'))
            
            if args.protocol in ['unreal', 'both']:
                # For Unreal protocol, use the specified unreal port or calculate from the server port
                ip, port = server
                if args.unreal_port != DEFAULT_UNREAL_QUERY_PORT:
                    unreal_port = args.unreal_port
                else:
                    # Try to use game port + offset for Unreal query
                    unreal_port = port
                    
                unreal_server = (ip, unreal_port)
                futures.append((executor.submit(query_unreal_server, unreal_server, args.timeout), 
                              unreal_server, 'unreal'))
        
        # Process results
        for future, server, protocol in futures:
            server_address_str = f"{server[0]}:{server[1]} ({protocol})"
            try:
                server_info = future.result()
                if server_info:
                    server_info_list.append(server_info)
            except Exception as e:
                logger.error(f"Error processing server {server_address_str}: {e}")
    
    # Sort servers by name
    server_info_list.sort(key=lambda x: x['name'])
    
    # Display results
    display_server_info(server_info_list)
    
    # Write output if we have results
    if server_info_list:
        write_output(server_info_list, args.output, args.format)
    
    logger.info(f"Queried {len(servers_to_query)} servers, got {len(server_info_list)} responses")
    logger.info("Script completed successfully")
    return 0

if __name__ == "__main__":
    sys.exit(main())


import os
import re
import time
import json
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('TileTracker')

class TileTracker:
    """
    Class to track and manage Last Oasis tile names for each server instance
    """
    def __init__(self, log_folder="C:\\lastoasis\\Mist\\Saved\\Logs", config_path="config.json"):
        self.log_folder = log_folder
        self.config_path = config_path
        self.tile_names = {}  # Map of server ID to tile name
        self.server_id_pattern = re.compile(r'-identifier=(\w+)(\d+)')
        self.tile_name_pattern = re.compile(r'LogPersistence: tile_name: (.+)')
        self.last_scan_time = {}  # Track when we last scanned each log file
        
        # Load config to get identifier prefix
        # Import config_utils here to avoid circular imports
        import config_utils
        
        try:
            # Use the safer config loading utility
            self.config, success, error = config_utils.load_config_safely(config_path)
            if success:
                self.identifier_prefix = self.config.get("identifier", "Disc0oasis")
            else:
                logger.error(f"Error loading config file: {error}")
                self.identifier_prefix = "Disc0oasis"  # Default fallback
        except Exception as e:
            logger.error(f"Error loading config file: {e}")
            self.identifier_prefix = "Disc0oasis"  # Default fallback
            
        # Initialize with any known mappings
        self.load_mappings()
            
    def load_mappings(self):
        """Load any saved mappings from a file"""
        try:
            if os.path.exists('tile_mappings.json'):
                with open('tile_mappings.json', 'r') as file:
                    self.tile_names = json.load(file)
                    logger.info(f"Loaded {len(self.tile_names)} tile mappings")
        except Exception as e:
            logger.error(f"Error loading tile mappings: {e}")
            
    def save_mappings(self):
        """Save the current mappings to a file"""
        try:
            with open('tile_mappings.json', 'w') as file:
                json.dump(self.tile_names, file, indent=4)
        except Exception as e:
            logger.error(f"Error saving tile mappings: {e}")
            
    def update_tile_name(self, server_id, tile_name):
        """Update the tile name for a given server ID"""
        if server_id not in self.tile_names or self.tile_names[server_id] != tile_name:
            logger.info(f"Updating tile name for {server_id}: {tile_name}")
            self.tile_names[server_id] = tile_name
            self.save_mappings()
            
    def get_tile_name(self, server_id, default=None):
        """Get the tile name for a given server ID, or return default if not found"""
        return self.tile_names.get(server_id, default)
    
    def get_tile_name_from_path(self, path):
        """Extract server ID from a command path and return the tile name"""
        match = self.server_id_pattern.search(path)
        if match:
            prefix, index = match.groups()
            server_id = prefix + index
            return self.get_tile_name(server_id, server_id)
        return None
        
    def scan_logs_for_tile_names(self):
        """Scan log files for tile name information"""
        log_files = [f for f in os.listdir(self.log_folder) if f.endswith('.log')]
        
        for log_file in log_files:
            file_path = os.path.join(self.log_folder, log_file)
            last_scan = self.last_scan_time.get(log_file, 0)
            
            try:
                # If file was modified since last scan
                if os.path.getmtime(file_path) > last_scan:
                    self._process_log_file(file_path, log_file)
            except Exception as e:
                logger.error(f"Error processing log file {log_file}: {e}")
                
    def _process_log_file(self, file_path, log_file):
        """Process a single log file to extract tile names"""
        try:
            with open(file_path, 'r', errors='ignore') as file:
                # If we've scanned this file before, seek to the end
                if log_file in self.last_scan_time:
                    file.seek(0, os.SEEK_END)
                    position = max(0, file.tell() - 50000)  # Read last 50KB to catch recent entries
                    file.seek(position, os.SEEK_SET)
                    # Skip partial line if we're in the middle of one
                    if position > 0:
                        file.readline()
                
                # Find server ID and tile name in the log
                server_id = None
                
                for line in file:
                    # Look for server ID in command line
                    id_match = self.server_id_pattern.search(line)
                    if id_match:
                        prefix, index = id_match.groups()
                        server_id = prefix + index
                    
                    # Look for tile name
                    name_match = self.tile_name_pattern.search(line)
                    if name_match and server_id:
                        tile_name = name_match.group(1).strip()
                        self.update_tile_name(server_id, tile_name)
                
                # Update last scan time
                self.last_scan_time[log_file] = time.time()
                
        except Exception as e:
            logger.error(f"Error reading log file {log_file}: {e}")
            
    def get_all_mappings(self):
        """Return all server ID to tile name mappings"""
        return self.tile_names.copy()

# Helper function for creating a global instance
_tracker = None

def get_tracker(log_folder=None, config_path=None):
    """Get or create a global TileTracker instance"""
    global _tracker
    if _tracker is None:
        _tracker = TileTracker(
            log_folder=log_folder or "C:\\lastoasis\\Mist\\Saved\\Logs",
            config_path=config_path or "config.json"
        )
    return _tracker


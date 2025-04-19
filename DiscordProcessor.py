import requests
import os
import json
import time
import logging
from PyQt5.QtCore import QObject, pyqtSignal

logger = logging.getLogger('LOManagerGUI.DiscordProcessor')

class DiscordProcessor(QObject):
    """Class to handle Discord webhook messaging and log monitoring
    
    This class provides functionality to:
    1. Send messages to Discord via webhooks with color coding
    2. Process game log files for events to be sent to Discord
    3. Send color-coded server status updates to Discord
    
    Configuration is provided via the config.json file, using the discord_webhook_url
    and discord_message_types settings.
    """
    
    # Signals
    messageProcessed = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    # Message Colors
    COLORS = {
        'chat': 3447003,   # Blue
        'join': 65280,     # Green
        'tile': 65280,     # Green
        'kill': 16776960,  # Yellow
        'test': 7506394,   # Gray
        'server_running': 65280,     # Green
        'server_stopped': 16711680,  # Red
        'server_starting': 3447003,  # Blue
        'server_stopping': 16753920  # Orange
    }
    
    def __init__(self, config=None):
        """Initialize the Discord processor
        
        Args:
            config (dict, optional): Configuration dictionary with Discord settings
        """
        super().__init__()
        self.config = config or {}
        self.webhook_url = None
        self.log_folder = None
        self.file_objects = {}
        self.running = False
        self.webhook_enabled = False
        self.webhook_validation_attempted = False
        self.webhook_error_reported = False  # To prevent repeated error messages
        self.message_types = {
            'chat': True,
            'join': True,
            'tile': True,
            'kill': True,
            'server_status': True
        }
        if config:
            self.update_config(config)
    def __del__(self):
        """Destructor to ensure file handles are closed properly when object is destroyed"""
        try:
            self.stop_monitoring()
        except Exception as e:
            logger.error(f"Error during Discord processor cleanup: {e}")
    
    def update_config(self, config):
        """Update configuration settings
        
        Args:
            config (dict): Configuration dictionary containing Discord settings
        """
        self.config = config
        
        # Check for webhook URL in both possible config locations for backward compatibility
        self.webhook_url = config.get('discord_webhook_url')
        if not self.webhook_url:
            # Check for legacy webhook URL field
            self.webhook_url = config.get('server_status_webhook')
            if self.webhook_url:
                logger.info("Using legacy server_status_webhook configuration. Please update to discord_webhook_url.")
        
        self.log_folder = os.path.join(
            config.get('folder_path', '').replace("Binaries\\Win64\\", ""),
            "Saved\\Logs"
        )
        self.message_types = config.get('discord_message_types', self.message_types)
        
        # Ensure server_status message type is in the dict
        if 'server_status' not in self.message_types:
            self.message_types['server_status'] = True
        
        # Reset webhook validation
        self.webhook_validation_attempted = False
        self.webhook_error_reported = False
        
        # Validate webhook if URL is provided
        if self.webhook_url:
            logger.info(f"Discord webhook URL configured, validating...")
            self.validate_webhook()
        else:
            logger.warning("Discord webhook URL not configured - notifications disabled")
            self.webhook_enabled = False
    
    def validate_webhook(self):
        """Validate the webhook URL by sending a test request
        
        Returns:
            bool: True if validation successful, False otherwise
        """
        if not self.webhook_url:
            self.webhook_enabled = False
            return False
        
        if self.webhook_validation_attempted:
            return self.webhook_enabled
        
        try:
            # Simple validation request - just check if the URL exists
            test_data = {
                "content": None,
                "embeds": [{
                    "description": "Webhook validation test",
                    "color": self.COLORS['test']
                }]
            }
            
            response = requests.post(
                self.webhook_url,
                headers={"Content-Type": "application/json"},
                data=json.dumps(test_data)
            )
            response.raise_for_status()
            
            self.webhook_enabled = True
            self.webhook_validation_attempted = True
            logger.info("Discord webhook validated successfully - notifications enabled")
            return True
            
        except requests.RequestException as e:
            self.webhook_enabled = False
            self.webhook_validation_attempted = True
            error_msg = f"Discord webhook validation failed: {e}"
            logger.error(error_msg)
            logger.warning("Discord notifications disabled due to webhook validation failure")
            self.error.emit(error_msg)
            return False
    
    def send_message(self, message, color, message_type=None):
        """Send a message to Discord via webhook
        
        Args:
            message (str): Message content to send
            color (int): Color code for the Discord embed
            message_type (str, optional): Type of message for filtering
            
        Returns:
            bool: True if message was successfully sent, False otherwise
        """
        # Check if webhook URL is configured
        if not self.webhook_url:
            if not self.webhook_error_reported:
                error_msg = "Discord webhook URL not configured"
                logger.warning(error_msg)
                self.error.emit(error_msg)
                self.webhook_error_reported = True
            return False
        
        # Validate webhook if not already validated
        if not self.webhook_validation_attempted:
            self.validate_webhook()
            
        # If webhook is disabled or validation failed, don't try to send
        if not self.webhook_enabled:
            return False
            
        # Check if this message type is enabled
        if message_type and not self.message_types.get(message_type, True):
            logger.debug(f"Message type {message_type} is disabled")
            return False
            
        data = {
            "embeds": [
                {
                    "description": message,
                    "color": color
                }
            ]
        }
        try:
            response = requests.post(
                self.webhook_url,
                headers={"Content-Type": "application/json"},
                data=json.dumps(data)
            )
            response.raise_for_status()
            
            # Reset error reported flag on successful send
            self.webhook_error_reported = False
            
            logger.info("Discord message sent successfully")
            self.messageProcessed.emit({
                'message': message,
                'color': color,
                'type': message_type,
                'success': True
            })
            return True
            
        except requests.RequestException as e:
            # Only log the first error to avoid spamming logs
            if not self.webhook_error_reported:
                error_msg = f"Failed to send Discord message: {e}"
                logger.error(error_msg)
                self.error.emit(error_msg)
                self.webhook_error_reported = True
                
                # Disable webhook after first error
                self.webhook_enabled = False
            return False
    
    def send_server_status(self, server_name, status):
        """Send a server status update to Discord with appropriate color coding
        
        Args:
            server_name (str): Name of the server
            status (str): Current status of the server (running, stopped, starting, stopping)
        
        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        # If Discord is not enabled, don't try to send
        if not self.webhook_enabled and self.webhook_validation_attempted:
            return False
        
        color_key = None
        status_lower = status.lower()
        
        # Determine the color based on status
        if status_lower == "running":
            color_key = 'server_running'
        elif status_lower == "stopped":
            color_key = 'server_stopped'
        elif status_lower == "starting":
            color_key = 'server_starting'
        elif status_lower == "stopping":
            color_key = 'server_stopping'
        else:
            # Default color if status doesn't match any known status
            color_key = 'test'
        
        # Format the message
        message = f"Server {server_name} is now {status}"
        
        # Send the message with the appropriate color
        return self.send_message(message, self.COLORS[color_key], 'server_status')
        
    def test_webhook(self):
        """Send a test message to verify webhook configuration"""
        # Reset validation flags to force a fresh check
        self.webhook_validation_attempted = False
        self.webhook_error_reported = False
        
        # Validate the webhook first
        if not self.validate_webhook():
            return False
            
        # If validation passed, send a test message
        return self.send_message(
            "Test message from Last Oasis Manager GUI",
            self.COLORS['test'],
            'test'
        )
    
    def process_line(self, line):
        """Process a log line and send appropriate Discord message"""
        try:
            if "Chat message from" in line and self.message_types.get('chat'):
                message = ' '.join(line.split()[4:])
                self.send_message(message, self.COLORS['chat'], 'chat')
                
            elif "Join succeeded" in line and self.message_types.get('join'):
                message = ' '.join(line.split()[3:])
                self.send_message(f"{message} Joined the server", self.COLORS['join'], 'join')
                
            elif "LogPersistence: tile_name:" in line and self.message_types.get('tile'):
                message = ' '.join(line.split()[2:])
                self.send_message(f"{message} Tile is ready to join", self.COLORS['tile'], 'tile')
                
            elif "killed" in line and "LogGame" in line and self.message_types.get('kill'):
                message = ' '.join(line.split()[1:])
                self.send_message(message, self.COLORS['kill'], 'kill')
                
        except Exception as e:
            logger.error(f"Error processing log line: {e}")
            self.error.emit(f"Error processing log line: {e}")
    
    def start_monitoring(self, log_files=None):
        """Start monitoring log files"""
        if not log_files:
            log_files = ["Mist.log", "Mist_2.log", "Mist_3.log"]
            
        if not self.log_folder:
            error_msg = "Log folder path not configured"
            logger.error(error_msg)
            self.error.emit(error_msg)
            return
            
        # Close any existing file objects
        self.stop_monitoring()
        
        # Open new file objects
        for log in log_files:
            try:
                file_path = os.path.join(self.log_folder, log)
                self.file_objects[log] = open(file_path, 'r')
                self.file_objects[log].seek(0, os.SEEK_END)
                logger.info(f"Monitoring log file: {file_path}")
            except FileNotFoundError:
                logger.warning(f"Log file not found: {log}")
                continue
            except Exception as e:
                logger.error(f"Error opening log file {log}: {e}")
                continue
        
        self.running = True
        
    def stop_monitoring(self):
        """Stop monitoring log files"""
        self.running = False
        for file in self.file_objects.values():
            try:
                file.close()
            except Exception as e:
                logger.error(f"Error closing log file: {e}")
        self.file_objects.clear()
        
    def check_logs(self):
        """Check logs for new entries (should be called periodically)"""
        if not self.running:
            return
            
        for log, file in self.file_objects.items():
            try:
                line = file.readline()
                if line:
                    line = line.strip()
                    logger.debug(f"Processing log line: {line}")
                    self.process_line(line)
            except Exception as e:
                logger.error(f"Error reading log file {log}: {e}")
                self.error.emit(f"Error reading log file {log}: {e}")
# ----------------------
# Backward Compatibility
# ----------------------

"""
This section provides backward compatibility functions for older code
that may directly call the Discord messaging functionality without using
the DiscordProcessor class directly.

Usage:
    from DiscordProcessor import send_discord_message
    
    # Send a message with a specific color
    send_discord_message("Hello, Discord!", 65280)  # Green message
"""

# Singleton processor instance for backward compatibility
_default_processor = None

def send_discord_message(message, color, message_type=None):
    """Send a Discord message using the default processor
    
    This function is provided for backward compatibility with older code.
    It creates a default processor if one doesn't exist yet.
    
    Args:
        message (str): The message to send
        color (int): The color code for the message
        message_type (str, optional): The type of message
        
    Returns:
        bool: True if message was sent successfully, False otherwise
    """
    global _default_processor
    
    # Create default processor if needed
    if _default_processor is None:
        try:
            from config_utils import load_config_safely
            config, success, _ = load_config_safely("config.json")
            if success:
                _default_processor = DiscordProcessor(config)
                logger.info("Created default Discord processor from config")
            else:
                logger.warning("Failed to load config, creating empty Discord processor")
                _default_processor = DiscordProcessor()
        except Exception as e:
            logger.error(f"Error creating default Discord processor: {e}")
            return False
    
    # Send the message with the specified color and type
    return _default_processor.send_message(message, color, message_type)

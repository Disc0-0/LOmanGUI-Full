import os
import threading
import time
import logging
import socket
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QGroupBox, QFrame, 
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QColor, QBrush

# Import existing LastOasisManager functionality
import LastOasisManager
from TileTracker import get_tracker
from DiscordProcessor import DiscordProcessor

logger = logging.getLogger('LOManagerGUI.ServerPanel')

class ServerStatusWidget(QFrame):
    """Widget to display status of an individual server tile"""
    
    def __init__(self, tile_id, parent=None, server_id=None):
        super().__init__(parent)
        self.tile_id = tile_id
        self.server_id = server_id or f"{LastOasisManager.config.get('identifier', 'Disc0oasis')}{tile_id}"
        self.status = "Unknown"
        self.tile_name = f"Tile {tile_id}"
        
        self.initUI()
        
    def initUI(self):
        """Initialize the UI components"""
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        
        layout = QVBoxLayout()
        
        # Server name and ID
        self.nameLabel = QLabel(f"{self.tile_name} ({self.server_id})")
        self.nameLabel.setAlignment(Qt.AlignCenter)
        self.nameLabel.setStyleSheet("font-weight: bold;")
        
        # Status indicator
        self.statusLabel = QLabel(f"Status: {self.status}")
        self.statusLabel.setAlignment(Qt.AlignCenter)
        
        # Control buttons
        buttonsLayout = QHBoxLayout()
        
        self.startButton = QPushButton("Start")
        self.stopButton = QPushButton("Stop")
        self.restartButton = QPushButton("Restart")
        
        # Connect signals
        self.startButton.clicked.connect(self.onStartClicked)
        self.stopButton.clicked.connect(self.onStopClicked)
        self.restartButton.clicked.connect(self.onRestartClicked)
        
        buttonsLayout.addWidget(self.startButton)
        buttonsLayout.addWidget(self.stopButton)
        buttonsLayout.addWidget(self.restartButton)
        
        # Add all widgets to layout
        layout.addWidget(self.nameLabel)
        layout.addWidget(self.statusLabel)
        layout.addLayout(buttonsLayout)
        
        self.setLayout(layout)
        
    def updateStatus(self, status):
        """Update the displayed status"""
        self.status = status
        self.statusLabel.setText(f"Status: {self.status}")
        
        # Always ensure the tile name is displayed correctly
        self.nameLabel.setText(f"{self.tile_name} ({self.server_id})")
        
        # Update UI based on status
        if self.status.lower() == "running":
            self.statusLabel.setStyleSheet("color: darkgreen; background-color: #E8F5E9; padding: 2px 4px; border-radius: 3px;")
            self.setStyleSheet("QFrame { border: 1px solid darkgreen; border-radius: 3px; }")
            self.startButton.setEnabled(False)
            self.stopButton.setEnabled(True)
            self.restartButton.setEnabled(True)
        elif self.status.lower() == "stopped":
            self.statusLabel.setStyleSheet("color: darkred; background-color: #FFEBEE; padding: 2px 4px; border-radius: 3px;")
            self.setStyleSheet("QFrame { border: 1px solid darkred; border-radius: 3px; }")
            self.startButton.setEnabled(True)
            self.stopButton.setEnabled(False)
            self.restartButton.setEnabled(False)
        elif self.status.lower() == "starting":
            self.statusLabel.setStyleSheet("color: darkblue; background-color: #E3F2FD; padding: 2px 4px; border-radius: 3px;")
            self.setStyleSheet("QFrame { border: 1px solid darkblue; border-radius: 3px; }")
            self.startButton.setEnabled(False)
            self.stopButton.setEnabled(True)
            self.restartButton.setEnabled(False)
        elif self.status.lower() == "stopping":
            self.statusLabel.setStyleSheet("color: #E65100; background-color: #FFF3E0; padding: 2px 4px; border-radius: 3px;")
            self.setStyleSheet("QFrame { border: 1px solid #E65100; border-radius: 3px; }")
            self.startButton.setEnabled(False)
            self.stopButton.setEnabled(False)
            self.restartButton.setEnabled(False)
        else:
            self.statusLabel.setStyleSheet("color: #333333; background-color: #F5F5F5; padding: 2px 4px; border-radius: 3px;")
            self.setStyleSheet("QFrame { border: 1px solid #9E9E9E; border-radius: 3px; }")
            self.startButton.setEnabled(True)
            self.stopButton.setEnabled(True)
            self.restartButton.setEnabled(True)
        
    def updateTileName(self, tracker=None):
        """Update the tile name from the tracker"""
        if tracker:
            # Get the tile name from the tracker with the server_id as fallback
            new_tile_name = tracker.get_tile_name(self.server_id, self.server_id)
            if new_tile_name != self.tile_name:
                self.tile_name = new_tile_name
                self.nameLabel.setText(f"{self.tile_name} ({self.server_id})")
    
    def onStartClicked(self):
        """Handle start button click"""
        logger.info(f"Starting tile {self.tile_id}")
        self.updateStatus("Starting")
        try:
            # Try to send WebSocket command if parent has access to WebSocket server
            parent = self.parent()
            if hasattr(parent, 'websocket_server') and parent.websocket_server and parent.websocket_server.is_running:
                # Create a new thread to avoid blocking UI
                threading.Thread(
                    target=lambda: parent.websocket_server.broadcast_event(
                        "command", "start_server", {"tile_id": self.tile_id}
                    )
                ).start()
            
            # Execute the command locally as well
            if not LastOasisManager.start_single_process(self.tile_id):
                # If start_single_process returned False, there was a configuration error
                error_msg = "Configuration error - check config.json"
                logger.error(f"Error starting tile {self.tile_id}: {error_msg}")
                self.updateStatus("Config Error")
                # Show error message to user
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.critical(self, "Configuration Error", 
                    "Server cannot be started due to missing configuration values.\n"
                    "Please check your config.json file and ensure all required fields are present.")
                return
        except Exception as e:
            logger.error(f"Error starting tile {self.tile_id}: {e}")
            self.updateStatus("Error")
    
    def onStopClicked(self):
        """Handle stop button click"""
        logger.info(f"Stopping tile {self.tile_id}")
        self.updateStatus("Stopping")
        try:
            # Try to send WebSocket command if parent has access to WebSocket server
            parent = self.parent()
            if hasattr(parent, 'websocket_server') and parent.websocket_server and parent.websocket_server.is_running:
                # Create a new thread to avoid blocking UI
                threading.Thread(
                    target=lambda: parent.websocket_server.broadcast_event(
                        "command", "stop_server", {"tile_id": self.tile_id}
                    )
                ).start()
            
            # Stop the specific process for this tile locally as well
            if self.tile_id < len(LastOasisManager.processes):
                if LastOasisManager.stop_events[self.tile_id] is not None:
                    LastOasisManager.stop_events[self.tile_id].set()
                if LastOasisManager.processes[self.tile_id] is not None:
                    LastOasisManager.processes[self.tile_id].join()
                # Set to None instead of removing
                LastOasisManager.stop_events[self.tile_id] = None
                LastOasisManager.processes[self.tile_id] = None
            else:
                logger.warning(f"Process index {self.tile_id} out of range")
        except Exception as e:
            logger.error(f"Error stopping tile {self.tile_id}: {e}")
            self.updateStatus("Error")
    
    def onRestartClicked(self):
        """Handle restart button click"""
        logger.info(f"Restarting tile {self.tile_id}")
        self.updateStatus("Restarting")
        try:
            # Try to send WebSocket command if parent has access to WebSocket server
            parent = self.parent()
            if hasattr(parent, 'websocket_server') and parent.websocket_server and parent.websocket_server.is_running:
                # Create a new thread to avoid blocking UI
                threading.Thread(
                    target=lambda: parent.websocket_server.broadcast_event(
                        "command", "restart_server", {"tile_id": self.tile_id}
                    )
                ).start()
            
            # Restart the specific process for this tile locally as well
            self.onStopClicked()
            time.sleep(1)
            self.onStartClicked()
        except Exception as e:
            logger.error(f"Error restarting tile {self.tile_id}: {e}")
            self.updateStatus("Error")


class ServerPanel(QWidget):
    """Panel for server management"""
    
    # Signal to broadcast server status updates
    statusUpdated = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = {}
        self.server_widgets = []
        self.websocket_server = None
        # Initialize TileTracker
        self.tile_tracker = get_tracker()
        # Initialize Discord processor
        self.discord_processor = None
        self.initUI()
        
    def initUI(self):
        """Initialize the UI components"""
        main_layout = QVBoxLayout()
        
        # Create server status group first - will be populated when config is loaded
        self.statusGroup = QGroupBox("Server Status")
        self.statusLayout = QGridLayout()
        self.statusGroup.setLayout(self.statusLayout)
        
        # Global controls
        control_group = QGroupBox("Global Controls")
        control_layout = QHBoxLayout()
        
        self.startAllButton = QPushButton("Start All Servers")
        self.stopAllButton = QPushButton("Stop All Servers")
        self.restartAllButton = QPushButton("Restart All Servers")
        self.checkUpdatesButton = QPushButton("Check for Updates")
        self.testDiscordButton = QPushButton("Test Discord")
        self.testDiscordButton.setToolTip("Send a test message to Discord to verify webhook configuration")
        
        # Connect signals
        self.startAllButton.clicked.connect(self.onStartAllClicked)
        self.stopAllButton.clicked.connect(self.onStopAllClicked)
        self.restartAllButton.clicked.connect(self.onRestartAllClicked)
        self.checkUpdatesButton.clicked.connect(self.onCheckUpdatesClicked)
        self.testDiscordButton.clicked.connect(self.onTestDiscordClicked)
        
        control_layout.addWidget(self.startAllButton)
        control_layout.addWidget(self.stopAllButton)
        control_layout.addWidget(self.restartAllButton)
        control_layout.addWidget(self.checkUpdatesButton)
        control_layout.addWidget(self.testDiscordButton)
        
        control_group.setLayout(control_layout)
        
        # Add widgets to main layout in correct order
        main_layout.addWidget(control_group)
        main_layout.addWidget(self.statusGroup)
        
        # Status summary
        self.summaryLabel = QLabel("No servers configured")
        main_layout.addWidget(self.summaryLabel)
        
        # Discord status indicator
        self.discordStatusLabel = QLabel("Discord: Not tested")
        self.discordStatusLabel.setStyleSheet("color: gray;")
        main_layout.addWidget(self.discordStatusLabel)
        # Set up timer for status updates
        self.timer = QTimer()
        self.timer.timeout.connect(self.updateServerStatus)
        self.timer.start(5000)  # Update every 5 seconds
        
        # Set the main layout
        self.setLayout(main_layout)
        
        # Connect the status updated signal to broadcast method
        self.statusUpdated.connect(self.broadcastServerStatus)
    
    def setWebSocketServer(self, websocket_server):
        """Set the WebSocket server reference"""
        self.websocket_server = websocket_server
    
    def setConfig(self, config):
        """Set configuration and initialize resources
        
        Args:
            config (dict): Configuration dictionary
        """
        self.config = config
        
        # Re-initialize tile tracker with updated config
        log_folder = os.path.join(config.get("folder_path", "").replace("Binaries\\Win64\\", ""), "Saved\\Logs")
        try:
            self.tile_tracker = get_tracker(
                log_folder=log_folder,
                config_path="config.json"
            )
            logger.info(f"TileTracker initialized with log folder: {log_folder}")
            
            # Force scan for tile names immediately to ensure names are available
            if self.tile_tracker:
                self.tile_tracker.scan_logs_for_tile_names()
        except Exception as e:
            logger.error(f"Failed to initialize TileTracker: {e}")
            self.tile_tracker = None
        
        # Initialize Discord processor with the new config
        try:
            self.discord_processor = DiscordProcessor(config)
            # Connect Discord processor signals
            if self.discord_processor:
                self.discord_processor.messageProcessed.connect(self.onDiscordMessageProcessed)
                self.discord_processor.error.connect(self.onDiscordError)
                # Update status label based on webhook validation
                if self.discord_processor.webhook_enabled:
                    self.updateDiscordStatus("ready", "Discord: Ready (webhook validated)")
                else:
                    self.updateDiscordStatus("error", "Discord: Not configured or invalid webhook")
        except Exception as e:
            logger.error(f"Failed to initialize Discord processor: {e}")
            self.discord_processor = None
            self.updateDiscordStatus("error", f"Discord: Error - {str(e)}")
        
        # Clear existing server widgets
        for widget in self.server_widgets:
            widget.deleteLater()
        self.server_widgets = []
        # Create server status widgets based on config
        if 'tile_num' in config:
            tile_num = config['tile_num']
            
            # Configure grid layout - 3 columns
            cols = 3
            rows = (tile_num + cols - 1) // cols  # Ceiling division
            
            for i in range(tile_num):
                # Create server ID for TileTracker lookup
                server_id = f"{config.get('identifier', 'Disc0oasis')}{i}"
                server_widget = ServerStatusWidget(i, self, server_id=server_id)
                # Update tile name from tracker
                if self.tile_tracker:
                    server_widget.updateTileName(self.tile_tracker)
                row = i // cols
                col = i % cols
                self.statusLayout.addWidget(server_widget, row, col)
                self.server_widgets.append(server_widget)
            
            self.summaryLabel.setText(f"{tile_num} servers configured")
    def getServerStatusData(self):
        """Get server status data for WebSocket broadcasts
        
        Returns:
            dict: Server status data with servers and summary information
        """
        servers_data = []
        for widget in self.server_widgets:
            servers_data.append({
                'tile_id': widget.tile_id,
                'server_id': widget.server_id,
                'tile_name': widget.tile_name,
                'status': widget.status
            })
        
        # Count running and stopped servers
        running = sum(1 for server in servers_data if server['status'].lower() == 'running')
        stopped = sum(1 for server in servers_data if server['status'].lower() == 'stopped')
        
        return {
            'servers': servers_data,
            'summary': {
                'total': len(self.server_widgets),
                'running': running,
                'stopped': stopped
            }
        }
    
    def updateServerStatus(self):
        """Update the status of all servers
        
        Returns:
            bool: True if status update was successful, False otherwise
        """
        try:
            # Scan for tile names if tracker is available
            if self.tile_tracker:
                self.tile_tracker.scan_logs_for_tile_names()
            else:
                # Try to re-initialize tile tracker if it's not available
                if self.config and 'folder_path' in self.config:
                    log_folder = os.path.join(self.config.get("folder_path", "").replace("Binaries\\Win64\\", ""), "Saved\\Logs")
                    self.tile_tracker = get_tracker(log_folder=log_folder, config_path="config.json")
                    logger.info("Re-initialized TileTracker")
            
            server_count = len(self.server_widgets)
            if server_count > 0:
                running = 0
                stopped = 0
                status_changed = False
                
                for widget in self.server_widgets:
                    # Check if this specific tile has a running process
                    is_running = (
                        len(LastOasisManager.processes) > widget.tile_id and
                        LastOasisManager.processes[widget.tile_id] is not None and
                        LastOasisManager.processes[widget.tile_id].is_alive()
                    )
                    
                    # Update tile name from tracker first
                    if self.tile_tracker:
                        widget.updateTileName(self.tile_tracker)
                    
                    # Check and update status
                    new_status = "Running" if is_running else "Stopped"
                    if widget.status != new_status:
                        # Status has changed, update and notify
                        widget.updateStatus(new_status)
                        self.send_discord_status(widget.tile_name, widget.server_id, new_status)
                        status_changed = True
                    else:
                        # Just refresh the UI
                        widget.updateStatus(widget.status)
                    
                    # Count for summary
                    if is_running:
                        running += 1
                    else:
                        stopped += 1
                
                # Update summary text
                self.summaryLabel.setText(f"Servers: {running} running, {stopped} stopped")
                
                # Emit status update signal (only if something changed or first update)
                if status_changed or not hasattr(self, '_last_status_update'):
                    self.statusUpdated.emit(self.getServerStatusData())
                    self._last_status_update = time.time()
                elif time.time() - self._last_status_update > 30:  # Broadcast at least every 30 seconds
                    self.statusUpdated.emit(self.getServerStatusData())
                    self._last_status_update = time.time()
                    
                return True
            return False
        except Exception as e:
            logger.error(f"Error updating server status: {e}")
            return False
    def onStartAllClicked(self):
        """Handle start all button click"""
        logger.info("Starting all servers")
        confirm = QMessageBox.question(
            self, 'Confirm Start All',
            "Are you sure you want to start all servers?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            try:
                LastOasisManager.start_processes()
                status_data = self.getServerStatusData()
                for widget in self.server_widgets:
                    widget.updateStatus("Starting")
                    # Send Discord notification
                    self.send_discord_status(widget.tile_name, widget.server_id, "Starting")
                
                # Broadcast status update only once
                self.statusUpdated.emit(status_data)
                self._last_status_update = time.time()
                
                return True
            except Exception as e:
                logger.error(f"Error starting servers: {e}")
                QMessageBox.critical(self, "Error", f"Failed to start servers: {str(e)}")
                return False

    def onStopAllClicked(self):
        """Handle stop all button click"""
        logger.info("Stopping all servers")
        confirm = QMessageBox.question(
            self, 'Confirm Stop All',
            "Are you sure you want to stop all servers?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            try:
                LastOasisManager.stop_processes()
                status_data = self.getServerStatusData()
                for widget in self.server_widgets:
                    widget.updateStatus("Stopping")
                # Send Discord notification
                    self.send_discord_status(widget.tile_name, widget.server_id, "Stopping")
                
                # Broadcast status update only once
                self.statusUpdated.emit(status_data)
                self._last_status_update = time.time()
                
                return True
            except Exception as e:
                logger.error(f"Error stopping servers: {e}")
                QMessageBox.critical(self, "Error", f"Failed to stop servers: {str(e)}")
                return False
    
    def onRestartAllClicked(self):
        """Handle restart all button click
        
        Returns:
            bool: True if restart was successful, False otherwise
        """
        logger.info("Restarting all servers")
        confirm = QMessageBox.question(
            self, 'Confirm Restart All',
            "Are you sure you want to restart all servers?\nThis will disconnect all users.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            try:
                # Use 5 second delay between stopping and starting for stability
                restart_success = LastOasisManager.restart_all_tiles(5)
                
                # Get current status data for broadcast
                status_data = self.getServerStatusData()
                
                # Update all widgets with restarting status
                for widget in self.server_widgets:
                    widget.updateStatus("Restarting")
                    # Send Discord notification
                    self.send_discord_status(widget.tile_name, widget.server_id, "Restarting")
                
                # Broadcast status update only once
                self.statusUpdated.emit(status_data)
                self._last_status_update = time.time()
                
                return restart_success
            except Exception as e:
                logger.error(f"Error restarting servers: {e}")
                QMessageBox.critical(self, "Error", f"Failed to restart servers: {str(e)}")
                return False
        
        return False
        
    def onCheckUpdatesClicked(self):
        """Handle check for updates button click
        
        Returns:
            bool: True if mod update check was successful, False otherwise
        """
        logger.info("Checking for updates")
        try:
            out_of_date, _ = LastOasisManager.check_mod_updates()
            if out_of_date:
                result = QMessageBox.question(
                    self, 
                    "Updates Available",
                    f"Found {len(out_of_date)} mods that need updates. Do you want to update them now?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                if result == QMessageBox.Yes:
                    # Restart to apply updates
                    status = LastOasisManager.restart_all_tiles(1)
                    # Update UI to reflect restart
                    status_data = self.getServerStatusData()
                    for widget in self.server_widgets:
                        widget.updateStatus("Restarting")
                        self.send_discord_status(widget.tile_name, widget.server_id, "Restarting for Updates")
                    
                    # Broadcast status
                    self.statusUpdated.emit(status_data)
                    return status
                else:
                    QMessageBox.information(
                        self,
                        "Updates Skipped",
                        "Update installation was skipped. Servers will continue running with current mod versions."
                    )
            else:
                QMessageBox.information(
                    self,
                    "No Updates",
                    "All mods are up to date."
                )
            return True
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
            QMessageBox.critical(self, "Error", f"Failed to check for updates: {str(e)}")
            return False
    
    def broadcastServerStatus(self, status_data):
        """Broadcast server status to all WebSocket clients
        
        Args:
            status_data (dict): Server status data from getServerStatusData
            
        Returns:
            bool: True if status was broadcast, False if no WebSocket server or not running
        """
        if hasattr(self, 'websocket_server') and self.websocket_server and self.websocket_server.is_running:
            self.websocket_server.broadcast_event("status", "server_status", status_data)
            return True
        return False
    def send_discord_status(self, tile_name, server_id, status):
        """Send server status update to Discord
        
        Args:
            tile_name (str): Name of the tile
            server_id (str): Server identifier
            status (str): Current server status
            
        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        # Don't send messages for blank or None values
        if not tile_name or not server_id or not status:
            logger.debug("Not sending Discord status - missing required parameters")
            return False
            
        try:
            if self.discord_processor is not None and self.discord_processor.webhook_enabled:
                server_name = f"{tile_name} ({server_id})"
                return self.discord_processor.send_server_status(server_name, status)
            else:
                if self.discord_processor is None:
                    logger.debug("Discord notifications not enabled - discord_processor is None")
                elif not self.discord_processor.webhook_enabled:
                    logger.debug("Discord notifications not enabled - webhook validation failed")
                return False
        except Exception as e:
            logger.error(f"Error sending Discord status notification: {e}")
            # Attempt to reconnect Discord processor if it failed
            if self.config and ('discord_webhook_url' in self.config or 'server_status_webhook' in self.config):
                try:
                    logger.info("Attempting to reconnect Discord processor")
                    self.discord_processor = DiscordProcessor(self.config)
                    self.discord_processor.messageProcessed.connect(self.onDiscordMessageProcessed)
                    self.discord_processor.error.connect(self.onDiscordError)
                except Exception as reconnect_error:
                    logger.error(f"Failed to reconnect Discord processor: {reconnect_error}")
            return False
    def onTestDiscordClicked(self):
        """Handle test Discord button click"""
        logger.info("Testing Discord webhook")
        try:
            if self.discord_processor is not None:
                self.updateDiscordStatus("testing", "Discord: Testing webhook...")
                # First check if the webhook is valid
                if not self.discord_processor.webhook_enabled and not self.discord_processor.webhook_validation_attempted:
                    logger.info("Validating Discord webhook first")
                    self.discord_processor.validate_webhook()
                
                # Send test message
                success = self.discord_processor.test_webhook()
                if success:
                    logger.info("Discord test message sent successfully")
                    self.updateDiscordStatus("success", "Discord: Test successful!")
                    QMessageBox.information(
                        self,
                        "Discord Test",
                        "Test message sent successfully to Discord.\nCheck your Discord channel to verify the message was received."
                    )
                else:
                    logger.warning("Discord test message failed")
                    self.updateDiscordStatus("error", "Discord: Test failed")
                    QMessageBox.warning(
                        self,
                        "Discord Test Failed",
                        "Failed to send test message to Discord.\n\nPossible reasons:\n- Webhook URL is invalid\n- Discord server is unreachable\n- Webhook permissions are incorrect\n\nCheck your configuration and try again."
                    )
            else:
                logger.warning("Discord processor not initialized")
                self.updateDiscordStatus("error", "Discord: Not initialized")
                QMessageBox.warning(
                    self,
                    "Discord Not Configured",
                    "Discord notifications are not configured.\n\nPlease update your configuration with a valid webhook URL."
                )
        except Exception as e:
            logger.error(f"Error testing Discord notifications: {e}")
            self.updateDiscordStatus("error", f"Discord: Error - {str(e)}")
            QMessageBox.critical(
                self,
                "Error",
                f"An error occurred while testing Discord notifications:\n{str(e)}"
            )
    
    def updateDiscordStatus(self, status, message):
        """Update the Discord status indicator
        
        Args:
            status (str): Status type ('ready', 'testing', 'success', 'error')
            message (str): Status message to display
        """
        self.discordStatusLabel.setText(message)
        
        if status == "ready":
            self.discordStatusLabel.setStyleSheet("color: #2196F3;")  # Blue
        elif status == "testing":
            self.discordStatusLabel.setStyleSheet("color: #FF9800;")  # Orange
        elif status == "success":
            self.discordStatusLabel.setStyleSheet("color: #4CAF50;")  # Green
        elif status == "error":
            self.discordStatusLabel.setStyleSheet("color: #F44336;")  # Red
        else:
            self.discordStatusLabel.setStyleSheet("color: gray;")
    
    def onDiscordMessageProcessed(self, message_data):
        """Handle Discord message processed signal"""
        if message_data.get('success', False):
            logger.info(f"Discord message sent: {message_data.get('message', '')}")
            self.updateDiscordStatus("success", "Discord: Last message sent successfully")
        else:
            logger.warning("Discord message failed")
            self.updateDiscordStatus("error", "Discord: Failed to send last message")
    
    def onDiscordError(self, error_message):
        """Handle Discord error signal"""
        logger.error(f"Discord error: {error_message}")
        self.updateDiscordStatus("error", f"Discord: Error - {error_message}")

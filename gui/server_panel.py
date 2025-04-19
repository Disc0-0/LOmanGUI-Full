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
            self.statusLabel.setStyleSheet("color: green;")
            self.startButton.setEnabled(False)
            self.stopButton.setEnabled(True)
            self.restartButton.setEnabled(True)
        elif self.status.lower() == "stopped":
            self.statusLabel.setStyleSheet("color: red;")
            self.startButton.setEnabled(True)
            self.stopButton.setEnabled(False)
            self.restartButton.setEnabled(False)
        elif self.status.lower() == "starting":
            self.statusLabel.setStyleSheet("color: blue;")
            self.startButton.setEnabled(False)
            self.stopButton.setEnabled(True)
            self.restartButton.setEnabled(False)
        elif self.status.lower() == "stopping":
            self.statusLabel.setStyleSheet("color: orange;")
            self.startButton.setEnabled(False)
            self.stopButton.setEnabled(False)
            self.restartButton.setEnabled(False)
        else:
            self.statusLabel.setStyleSheet("")
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
        self.initUI()
        
    def initUI(self):
        """Initialize the UI components"""
        main_layout = QVBoxLayout()
        
        # Global controls
        control_group = QGroupBox("Global Controls")
        control_layout = QHBoxLayout()
        
        self.startAllButton = QPushButton("Start All Servers")
        self.stopAllButton = QPushButton("Stop All Servers")
        self.restartAllButton = QPushButton("Restart All Servers")
        self.checkUpdatesButton = QPushButton("Check for Updates")
        
        # Connect signals
        self.startAllButton.clicked.connect(self.onStartAllClicked)
        self.stopAllButton.clicked.connect(self.onStopAllClicked)
        self.restartAllButton.clicked.connect(self.onRestartAllClicked)
        self.checkUpdatesButton.clicked.connect(self.onCheckUpdatesClicked)
        
        control_layout.addWidget(self.startAllButton)
        control_layout.addWidget(self.stopAllButton)
        control_layout.addWidget(self.restartAllButton)
        control_layout.addWidget(self.checkUpdatesButton)
        
        control_group.setLayout(control_layout)
        main_layout.addWidget(control_group)
        
        # Server status grid - will be populated when config is loaded
        self.statusGroup = QGroupBox("Server Status")
        self.statusLayout = QGridLayout()
        self.statusGroup.setLayout(self.statusLayout)
        
        main_layout.addWidget(self.statusGroup)
        
        # Status summary
        self.summaryLabel = QLabel("No servers configured")
        main_layout.addWidget(self.summaryLabel)
        
        # Set up timer for status updates
        self.timer = QTimer()
        self.timer.timeout.connect(self.updateServerStatus)
        self.timer.start(5000)  # Update every 5 seconds
        
        
        self.setLayout(main_layout)
        
        # Connect the status updated signal to broadcast method
        self.statusUpdated.connect(self.broadcastServerStatus)
    
    def setWebSocketServer(self, websocket_server):
        """Set the WebSocket server reference"""
        self.websocket_server = websocket_server
    
    def setConfig(self, config):
        self.config = config
        
        # Re-initialize tile tracker with updated config
        self.tile_tracker = get_tracker(
            log_folder=os.path.join(config.get("folder_path", "").replace("Binaries\\Win64\\", ""), "Saved\\Logs"),
            config_path="config.json"
        )
        
        # Force scan for tile names
        if self.tile_tracker:
            self.tile_tracker.scan_logs_for_tile_names()
        
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
                server_widget = ServerStatusWidget(i, server_id=server_id)
                # Update tile name from tracker
                if self.tile_tracker:
                    server_widget.updateTileName(self.tile_tracker)
                row = i // cols
                col = i % cols
                self.statusLayout.addWidget(server_widget, row, col)
                self.server_widgets.append(server_widget)
            
            
            self.summaryLabel.setText(f"{tile_num} servers configured")
        else:
            self.summaryLabel.setText("No servers configured")
    
    def getServerStatusData(self):
        """Get server status data for WebSocket broadcasts"""
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
        """Update the status of all servers"""
        if self.tile_tracker:
            self.tile_tracker.scan_logs_for_tile_names()
            
        server_count = len(self.server_widgets)
        if server_count > 0:
            running = 0
            stopped = 0
            
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
                
                if is_running:
                    if widget.status != "Running":
                        widget.updateStatus("Running")
                    else:
                        # Force UI update for consistency even if status didn't change
                        widget.updateStatus(widget.status)
                    running += 1
                else:
                    if widget.status != "Stopped":
                        widget.updateStatus("Stopped")
                    else:
                        # Force UI update for consistency even if status didn't change
                        widget.updateStatus(widget.status)
                    stopped += 1
                    
            self.summaryLabel.setText(f"Servers: {running} running, {stopped} stopped")
            
            # Emit status update signal
            self.statusUpdated.emit(self.getServerStatusData())
    
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
                for widget in self.server_widgets:
                    widget.updateStatus("Starting")
                
                # Broadcast status update
                self.statusUpdated.emit(self.getServerStatusData())
            except Exception as e:
                logger.error(f"Error starting servers: {e}")
                QMessageBox.critical(self, "Error", f"Failed to start servers: {str(e)}")

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
                for widget in self.server_widgets:
                    widget.updateStatus("Stopping")
                
                # Broadcast status update
                self.statusUpdated.emit(self.getServerStatusData())
            except Exception as e:
                logger.error(f"Error stopping servers: {e}")
                QMessageBox.critical(self, "Error", f"Failed to stop servers: {str(e)}")
    def onRestartAllClicked(self):
        """Handle restart all button click"""
        logger.info("Restarting all servers")
        confirm = QMessageBox.question(
            self, 'Confirm Restart All',
            "Are you sure you want to restart all servers?\nThis will disconnect all users.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            try:
                LastOasisManager.restart_all_tiles(1)
                for widget in self.server_widgets:
                    widget.updateStatus("Restarting")
                
                # Broadcast status update
                self.statusUpdated.emit(self.getServerStatusData())
            except Exception as e:
                logger.error(f"Error restarting servers: {e}")
                QMessageBox.critical(self, "Error", f"Failed to restart servers: {str(e)}")
    
    def onCheckUpdatesClicked(self):
        """Handle check for updates button click"""
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
                    LastOasisManager.restart_all_tiles(1)
            else:
                QMessageBox.information(
                    self,
                    "No Updates",
                    "All mods are up to date."
                )
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
            QMessageBox.critical(self, "Error", f"Failed to check for updates: {str(e)}")
    
    def broadcastServerStatus(self, status_data):
        """Broadcast server status to all WebSocket clients"""
        if hasattr(self, 'websocket_server') and self.websocket_server and self.websocket_server.is_running:
            self.websocket_server.broadcast_event("status", "server_status", status_data)
    
    def updateFromStatusMessage(self, message_data):
        """Update server status from a WebSocket status message"""
        try:
            # Check if we have servers data
            if 'servers' in message_data:
                server_data = message_data['servers']
                
                # Update each server widget
                for server_info in server_data:
                    tile_id = server_info.get('tile_id')
                    status = server_info.get('status')
                    
                    # Find the corresponding widget
                    for widget in self.server_widgets:
                        if widget.tile_id == tile_id:
                            # Only update if status changed
                            if widget.status != status:
                                widget.updateStatus(status)
                            break
                
                # Update summary if available
                if 'summary' in message_data:
                    summary = message_data['summary']
                    running = summary.get('running', 0)
                    stopped = summary.get('stopped', 0)
                    self.summaryLabel.setText(f"Servers: {running} running, {stopped} stopped")
        except Exception as e:
            logger.error(f"Error updating from WebSocket status message: {e}")

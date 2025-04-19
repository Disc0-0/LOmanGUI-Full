import os
import json
import logging
import time
import threading
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QGroupBox, QFrame, 
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QTextEdit, QComboBox,
    QListWidget, QListWidgetItem, QSplitter
)
from PyQt5.QtCore import Qt, QDateTime, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QColor, QBrush, QFont

# Import admin writer functionality
import admin_writer

logger = logging.getLogger('LOManagerGUI.AdminPanel')

class AdminPanel(QWidget):
    """Panel for sending and managing admin messages"""
    
    # Signal for broadcasting message updates
    messageUpdated = pyqtSignal(dict)
    historyUpdated = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = {}
        self.message_history = []
        self.websocket_server = None
        self.initUI()
        
    def initUI(self):
        """Initialize the UI components"""
        main_layout = QVBoxLayout()
        
        # Create message composer section
        composer_group = QGroupBox("Message Composer")
        composer_layout = QVBoxLayout()
        
        # Text area for message input
        self.messageEdit = QTextEdit()
        self.messageEdit.setPlaceholderText("Enter your admin message here...")
        self.messageEdit.setMaximumHeight(150)
        composer_layout.addWidget(QLabel("Message:"))
        composer_layout.addWidget(self.messageEdit)
        
        # Controls for sending message
        controls_layout = QHBoxLayout()
        
        # Target selection
        target_layout = QVBoxLayout()
        target_layout.addWidget(QLabel("Send to:"))
        self.targetCombo = QComboBox()
        self.targetCombo.addItem("All Tiles", -1)  # -1 means all tiles
        # Individual tiles will be added when config is loaded
        target_layout.addWidget(self.targetCombo)
        controls_layout.addLayout(target_layout)
        
        # Send button
        self.sendButton = QPushButton("Send Message")
        self.sendButton.clicked.connect(self.onSendClicked)
        controls_layout.addWidget(self.sendButton)
        
        # Clear button
        self.clearButton = QPushButton("Clear")
        self.clearButton.clicked.connect(self.onClearClicked)
        controls_layout.addWidget(self.clearButton)
        
        composer_layout.addLayout(controls_layout)
        composer_group.setLayout(composer_layout)
        main_layout.addWidget(composer_group)
        
        # Create quick messages section
        quick_group = QGroupBox("Quick Messages")
        quick_layout = QGridLayout()
        
        # Define common admin messages
        quick_messages = [
            "Server restart in 5 minutes",
            "Server restart in 1 minute",
            "Server maintenance starting soon",
            "Thanks for playing!",
            "Please report bugs on Discord",
            "Welcome to the server!"
        ]
        
        # Create buttons in a grid (3 columns)
        cols = 3
        for i, message in enumerate(quick_messages):
            btn = QPushButton(message)
            # Using a lambda with default arg to avoid late binding issue
            btn.clicked.connect(lambda checked, msg=message: self.setQuickMessage(msg))
            row, col = i // cols, i % cols
            quick_layout.addWidget(btn, row, col)
        
        quick_group.setLayout(quick_layout)
        main_layout.addWidget(quick_group)
        
        # Message history section
        history_group = QGroupBox("Message History")
        history_layout = QVBoxLayout()
        
        self.historyList = QListWidget()
        self.historyList.setAlternatingRowColors(True)
        history_layout.addWidget(self.historyList)
        
        # Clear history button
        self.clearHistoryButton = QPushButton("Clear History")
        self.clearHistoryButton.clicked.connect(self.onClearHistoryClicked)
        history_layout.addWidget(self.clearHistoryButton)
        
        
        history_group.setLayout(history_layout)
        main_layout.addWidget(history_group)
        
        # Set the main layout for the panel
        self.setLayout(main_layout)
    
    def setWebSocketServer(self, websocket_server):
        self.websocket_server = websocket_server
    
    def setConfig(self, config):
        """Set configuration and update UI accordingly"""
        self.config = config
        
        # Clear existing tile options (except "All Tiles")
        while self.targetCombo.count() > 1:
            self.targetCombo.removeItem(1)
        
        # Add tiles based on config
        if 'tile_num' in config:
            tile_num = config['tile_num']
            for i in range(tile_num):
                self.targetCombo.addItem(f"Tile {i}", i)
        
        # Broadcast available targets to WebSocket clients
        self.broadcastTargets()
    
    def onSendClicked(self):
        """Handle send button click"""
        message = self.messageEdit.toPlainText().strip()
        if not message:
            QMessageBox.warning(self, "Empty Message", "Please enter a message to send.")
            return
        
        target_index = self.targetCombo.currentIndex()
        target_id = self.targetCombo.itemData(target_index)
        
        # Confirm before sending
        target_text = "all tiles" if target_id == -1 else f"Tile {target_id}"
        confirm = QMessageBox.question(
            self, 'Confirm Send',
            f"Send this message to {target_text}?\n\n{message}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            self.sendMessage(message, target_id)
    
    def sendMessage(self, message, target_id):
        """Send the admin message"""
        try:
            # Create a thread to avoid UI freezing during the sleep in admin_writer
            threading.Thread(
                target=self._send_message_thread,
                args=(message, target_id),
                daemon=True
            ).start()
            
            # Add to history immediately for UI responsiveness
            timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
            target_text = "All Tiles" if target_id == -1 else f"Tile {target_id}"
            history_text = f"{timestamp} - {target_text}: {message}"
            
            self.message_history.append(history_text)
            self.updateHistoryList()
            
            # Clear the message input
            self.messageEdit.clear()
            
            # Broadcast the message to WebSocket clients
            self.messageUpdated.emit({
                "message": message,
                "target_id": target_id,
                "target_text": target_text,
                "timestamp": timestamp
            })
            
        except Exception as e:
            logger.error(f"Error sending admin message: {e}")
            QMessageBox.critical(
                self, 
                "Error Sending Message", 
                f"Failed to send admin message: {str(e)}"
            )
    
    def _send_message_thread(self, message, target_id):
        """Thread function to send the message without blocking UI"""
        try:
            folder_path = self.config.get('folder_path', '')
            if not folder_path:
                raise ValueError("Server folder path not configured")
            
            if target_id == -1:
                # Send to all tiles
                tile_num = self.config.get('tile_num', 1)
                for i in range(tile_num):
                    admin_writer.write(message, folder_path, i)
                    logger.info(f"Admin message sent to tile {i}: {message}")
            else:
                # Send to specific tile
                admin_writer.write(message, folder_path, target_id)
                logger.info(f"Admin message sent to tile {target_id}: {message}")
                
        except Exception as e:
            logger.error(f"Error in message thread: {e}")
            # We can't directly call QMessageBox from a non-GUI thread
            # In a more complete implementation, we would use signals to show errors
    
    def onClearClicked(self):
        """Clear the message input field"""
        self.messageEdit.clear()
    
    def setQuickMessage(self, message):
        """Set a quick message in the text edit"""
        self.messageEdit.setText(message)
        # Focus the text edit to allow for easy editing
        self.messageEdit.setFocus()
    
    def updateHistoryList(self):
        """Update the message history list"""
        self.historyList.clear()
        # Add items in reverse order (newest first)
        for message in reversed(self.message_history):
            self.historyList.addItem(message)
            
        # Broadcast history update
        self.historyUpdated.emit(self.getHistoryData())
    
    def onClearHistoryClicked(self):
        """Clear the message history"""
        confirm = QMessageBox.question(
            self, 'Clear History',
            "Are you sure you want to clear the message history?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            self.message_history.clear()
            self.historyList.clear()
            
            # Broadcast history cleared
            self.historyUpdated.emit(self.getHistoryData())

    def getHistoryData(self):
        """Get message history data for WebSocket broadcasts"""
        return {
            "history": self.message_history,
            "count": len(self.message_history)
        }
        
    def getTargetsData(self):
        """Get target tiles data for WebSocket broadcasts"""
        targets = []
        
        # Add all tiles option
        targets.append({
            "id": -1,
            "name": "All Tiles",
            "description": "Send to all server tiles"
        })
        
        # Add individual tiles
        if 'tile_num' in self.config:
            tile_num = self.config.get('tile_num', 0)
            for i in range(tile_num):
                targets.append({
                    "id": i,
                    "name": f"Tile {i}",
                    "description": f"Send only to tile {i}"
                })
        
        return {
            "targets": targets,
            "count": len(targets)
        }
    
    def broadcastMessageUpdate(self, message_data):
        """Broadcast message update to all WebSocket clients"""
        if hasattr(self, 'websocket_server') and self.websocket_server and self.websocket_server.is_running:
            self.websocket_server.broadcast_event("admin", "message_sent", message_data)
    
    def broadcastHistoryUpdate(self, history_data):
        """Broadcast history update to all WebSocket clients"""
        if hasattr(self, 'websocket_server') and self.websocket_server and self.websocket_server.is_running:
            self.websocket_server.broadcast_event("admin", "history_update", history_data)
    
    def broadcastTargets(self):
        """Broadcast available targets to all WebSocket clients"""
        if hasattr(self, 'websocket_server') and self.websocket_server and self.websocket_server.is_running:
            self.websocket_server.broadcast_event("admin", "targets_update", self.getTargetsData())
    
    def updateFromStatusMessage(self, message_data):
        """Update from a WebSocket status message"""
        try:
            # Handle message history updates
            if 'history' in message_data and isinstance(message_data['history'], list):
                # For now, we don't automatically update the local history from remote updates
                # This would be a design decision - whether to merge histories or not
                pass
        except Exception as e:
            logger.error(f"Error updating from WebSocket status message: {e}")
    
    def handleWebSocketCommand(self, command, data):
        """Handle commands received from WebSocket clients"""
        try:
            if command == "send_message":
                message = data.get("message", "").strip()
                target_id = data.get("target_id", -1)
                
                if not message:
                    return False, "Message cannot be empty"
                
                # Send the message
                threading.Thread(
                    target=self._send_message_thread,
                    args=(message, target_id),
                    daemon=True
                ).start()
                
                # Add to history
                timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
                target_text = "All Tiles" if target_id == -1 else f"Tile {target_id}"
                history_text = f"{timestamp} - {target_text}: {message}"
                
                self.message_history.append(history_text)
                self.updateHistoryList()
                
                return True, {
                    "message": "Message sent successfully",
                    "target": target_text,
                    "timestamp": timestamp
                }
            
            elif command == "get_history":
                return True, self.getHistoryData()
            
            elif command == "clear_history":
                self.message_history.clear()
                self.historyList.clear()
                self.historyUpdated.emit(self.getHistoryData())
                return True, {"message": "History cleared"}
            
            elif command == "get_targets":
                return True, self.getTargetsData()
            
            return False, f"Unknown command: {command}"
        except Exception as e:
            logger.error(f"Error handling WebSocket command {command}: {e}")
            return False, f"Error: {str(e)}"

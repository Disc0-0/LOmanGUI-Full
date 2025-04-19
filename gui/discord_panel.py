import os
import json
import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QGroupBox, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QTextEdit, QCheckBox,
    QListWidget, QListWidgetItem
)
from PyQt5.QtCore import Qt, QDateTime, pyqtSignal, QTimer
from PyQt5.QtGui import QColor, QBrush, QFont

# Import Discord processor functionality
from DiscordProcessor import DiscordProcessor

logger = logging.getLogger('LOManagerGUI.DiscordPanel')

class DiscordPanel(QWidget):
    """Panel for managing Discord output settings and message history"""
    
    # Signals for updates
    configUpdated = pyqtSignal(dict)
    messageReceived = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = {}
        self.message_history = []
        self.processor = DiscordProcessor()
        self.monitoring_timer = QTimer(self)
        self.monitoring_timer.timeout.connect(self.check_logs)
        self.monitoring_timer.setInterval(100)  # Check every 100ms
        
        # Connect processor signals
        self.processor.messageProcessed.connect(self.on_message_processed)
        self.processor.error.connect(self.on_processor_error)
        
        self.initUI()
        
    def initUI(self):
        """Initialize the UI components"""
        main_layout = QVBoxLayout()
        
        # Webhook Configuration Section
        webhook_group = QGroupBox("Discord Webhook Configuration")
        webhook_layout = QVBoxLayout()
        
        # Webhook URL input
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("Webhook URL:"))
        self.webhookInput = QLineEdit()
        self.webhookInput.setPlaceholderText("Enter Discord webhook URL...")
        url_layout.addWidget(self.webhookInput)
        
        # Test webhook button
        self.testButton = QPushButton("Test Webhook")
        self.testButton.clicked.connect(self.onTestWebhook)
        url_layout.addWidget(self.testButton)
        
        # Save webhook button
        self.saveButton = QPushButton("Save")
        self.saveButton.clicked.connect(self.onSaveConfig)
        url_layout.addWidget(self.saveButton)
        
        webhook_layout.addLayout(url_layout)
        webhook_group.setLayout(webhook_layout)
        main_layout.addWidget(webhook_group)
        
        # Message Types Configuration
        types_group = QGroupBox("Message Types")
        types_layout = QGridLayout()
        
        # Create checkboxes for different message types
        self.typeCheckboxes = {
            "chat": QCheckBox("Chat Messages (Blue)"),
            "join": QCheckBox("Player Joins (Green)"),
            "tile": QCheckBox("Tile Ready (Green)"),
            "kill": QCheckBox("Kill Feed (Yellow)")
        }
        
        # Add checkboxes to grid layout
        for i, (key, checkbox) in enumerate(self.typeCheckboxes.items()):
            row, col = i // 2, i % 2
            types_layout.addWidget(checkbox, row, col)
            checkbox.setChecked(True)  # Default to enabled
            checkbox.stateChanged.connect(self.onMessageTypeChanged)
        
        types_group.setLayout(types_layout)
        main_layout.addWidget(types_group)
        
        # Message Preview Section
        preview_group = QGroupBox("Message Preview")
        preview_layout = QVBoxLayout()
        
        self.previewList = QListWidget()
        self.previewList.setAlternatingRowColors(True)
        preview_layout.addWidget(self.previewList)
        
        # Clear preview button
        self.clearPreviewButton = QPushButton("Clear Preview")
        self.clearPreviewButton.clicked.connect(self.onClearPreview)
        preview_layout.addWidget(self.clearPreviewButton)
        
        preview_group.setLayout(preview_layout)
        main_layout.addWidget(preview_group)
        
        self.setLayout(main_layout)
    
    def setConfig(self, config):
        """Set configuration and update UI accordingly"""
        self.config = config
        
        # Load webhook URL from config
        webhook_url = config.get('discord_webhook_url', '')
        self.webhookInput.setText(webhook_url)
        
        # Load message type settings
        message_types = config.get('discord_message_types', {})
        for msg_type, checkbox in self.typeCheckboxes.items():
            checkbox.setChecked(message_types.get(msg_type, True))
            
        # Update processor config
        self.processor.update_config(config)
        
        # Start monitoring if webhook is configured
        if webhook_url:
            self.processor.start_monitoring()
            self.monitoring_timer.start()
        else:
            self.monitoring_timer.stop()
            self.processor.stop_monitoring()
    
    def onSaveConfig(self):
        """Save webhook configuration"""
        webhook_url = self.webhookInput.text().strip()
        
        # Update config
        self.config['discord_webhook_url'] = webhook_url
        self.config['discord_message_types'] = {
            msg_type: checkbox.isChecked()
            for msg_type, checkbox in self.typeCheckboxes.items()
        }
        
        # Emit config updated signal
        self.configUpdated.emit(self.config)
        
        QMessageBox.information(self, "Configuration Saved", "Discord settings have been saved.")
    
    def onTestWebhook(self):
        """Test the webhook connection"""
        webhook_url = self.webhookInput.text().strip()
        if not webhook_url:
            QMessageBox.warning(self, "Invalid URL", "Please enter a webhook URL first.")
            return
        
        # Update processor with current webhook URL
        self.processor.webhook_url = webhook_url
        if self.processor.test_webhook():
            QMessageBox.information(self, "Test Successful", "Test message sent successfully!")
        # Error handling is done through the error signal
    
    def onMessageTypeChanged(self):
        """Handle message type checkbox changes"""
        # Auto-save configuration when types are changed
        self.onSaveConfig()
    
    def onClearPreview(self):
        """Clear the message preview list"""
        confirm = QMessageBox.question(
            self, 'Clear Preview',
            "Are you sure you want to clear the message preview?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            self.previewList.clear()
            self.message_history.clear()
    
    def addMessage(self, message, color_name, timestamp=None):
        """Add a message to the preview list"""
        if not timestamp:
            timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
        
        history_text = f"{timestamp} - {color_name}: {message}"
        self.message_history.append(history_text)
        
        # Add to preview list
        item = QListWidgetItem(history_text)
        self.previewList.insertItem(0, item)  # Add at top
        
        # Keep only last 100 messages
        while self.previewList.count() > 100:
            self.previewList.takeItem(self.previewList.count() - 1)
    
    def shouldProcessMessageType(self, message_type):
        """Check if a message type should be processed based on settings"""
        return self.typeCheckboxes.get(message_type, QCheckBox()).isChecked()
        
    def check_logs(self):
        """Periodic check for new log entries"""
        self.processor.check_logs()
        
    def on_message_processed(self, message_data):
        """Handle processed message from Discord processor"""
        message = message_data.get('message', '')
        msg_type = message_data.get('type', 'unknown')
        color_name = self.get_color_name(message_data.get('color', 0))
        self.addMessage(message, color_name)
        
    def on_processor_error(self, error_message):
        """Handle error from Discord processor"""
        QMessageBox.critical(self, "Discord Error", error_message)
        
    def get_color_name(self, color_value):
        """Get readable name for color value"""
        color_names = {
            3447003: "Chat",     # Blue
            65280: "Event",      # Green
            16776960: "Kill",    # Yellow
            7506394: "System"    # Gray
        }
        return color_names.get(color_value, "Message")
        
    def closeEvent(self, event):
        """Handle panel close event"""
        self.monitoring_timer.stop()
        self.processor.stop_monitoring()
        super().closeEvent(event)

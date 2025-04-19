import os
import json
import logging
import shutil
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QGroupBox, QLineEdit,
    QSpinBox, QFileDialog, QMessageBox,
    QFormLayout, QScrollArea, QFrame, QCheckBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor

logger = logging.getLogger('LOManagerGUI.ConfigPanel')

class ValidatingLineEdit(QLineEdit):
    """Line edit with validation and visual feedback"""
    
    validationChanged = pyqtSignal(bool)
    
    def __init__(self, validator_func=None, parent=None):
        super().__init__(parent)
        self.validator_func = validator_func
        self.valid = True
        self.textChanged.connect(self.validate)
        
    def validate(self):
        """Validate the current text and update styling"""
        if self.validator_func:
            valid, message = self.validator_func(self.text())
            self.valid = valid
            
            if valid:
                self.setStyleSheet("")
                self.setToolTip("")
            else:
                self.setStyleSheet("background-color: #FFDDDD;")
                self.setToolTip(message)
                
            self.validationChanged.emit(valid)
        else:
            self.valid = True
            self.setStyleSheet("")
            self.setToolTip("")
            self.validationChanged.emit(True)

class PathLineEdit(QWidget):
    """Line edit with browse button for paths"""
    
    validationChanged = pyqtSignal(bool)
    
    def __init__(self, dialog_type="dir", validator_func=None, parent=None):
        super().__init__(parent)
        self.dialog_type = dialog_type  # "dir" or "file"
        self.validator_func = validator_func
        self.valid = True
        
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.lineEdit = ValidatingLineEdit(validator_func, self)
        self.lineEdit.validationChanged.connect(self.onValidationChanged)
        
        self.browseButton = QPushButton("Browse...")
        self.browseButton.clicked.connect(self.browse)
        
        layout.addWidget(self.lineEdit)
        layout.addWidget(self.browseButton)
        
        self.setLayout(layout)
    
    def text(self):
        """Get the current text"""
        return self.lineEdit.text()
    
    def setText(self, text):
        """Set the text"""
        self.lineEdit.setText(text)
    
    def browse(self):
        """Open file or directory browser dialog"""
        current_path = self.lineEdit.text()
        
        if self.dialog_type == "dir":
            path = QFileDialog.getExistingDirectory(
                self, "Select Directory", current_path
            )
        else:  # file
            path, _ = QFileDialog.getOpenFileName(
                self, "Select File", current_path
            )
        
        if path:
            # Make sure path ends with a backslash for directories
            if self.dialog_type == "dir" and not path.endswith(('\\', '/')):
                path = path + '\\'
            
            self.lineEdit.setText(path)
    
    def onValidationChanged(self, valid):
        """Handle validation change"""
        self.valid = valid
        self.validationChanged.emit(valid)

class ConfigPanel(QWidget):
    """Panel for configuration editing"""
    
    # Signal to broadcast config updates
    configUpdated = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = {}
        self.config_widgets = {}
        self.valid = True
        self.websocket_server = None
        self.initUI()
    
    def initUI(self):
        """Initialize the UI components"""
        main_layout = QVBoxLayout()
        
        # Buttons for save/reset
        buttons_layout = QHBoxLayout()
        
        self.saveButton = QPushButton("Save Configuration")
        self.resetButton = QPushButton("Reset to Loaded")
        self.backupButton = QPushButton("Backup Configuration")
        self.browseConfigButton = QPushButton("Browse Config File")
        
        # Connect signals
        self.saveButton.clicked.connect(self.onSaveClicked)
        self.resetButton.clicked.connect(self.onResetClicked)
        self.backupButton.clicked.connect(self.onBackupClicked)
        self.browseConfigButton.clicked.connect(self.onBrowseConfigClicked)
        
        buttons_layout.addWidget(self.saveButton)
        buttons_layout.addWidget(self.resetButton)
        buttons_layout.addWidget(self.backupButton)
        buttons_layout.addWidget(self.browseConfigButton)
        
        main_layout.addLayout(buttons_layout)
        
        # Create scroll area for configuration form
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        # Create form group inside scroll area
        form_container = QWidget()
        self.form_group = QGroupBox("Configuration Settings")
        form_layout = QFormLayout()
        self.form_group.setLayout(form_layout)
        
        # Add form group to container
        container_layout = QVBoxLayout()
        container_layout.addWidget(self.form_group)
        form_container.setLayout(container_layout)
        
        # Set container as scroll area widget
        scroll.setWidget(form_container)
        
        # Add scroll area to main layout
        main_layout.addWidget(scroll)
        
        # Status message
        self.statusLabel = QLabel("No configuration loaded")
        self.statusLabel.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.statusLabel)
        main_layout.addWidget(self.statusLabel)
        
        self.setLayout(main_layout)
        
        # Connect signals for WebSocket communication
        self.configUpdated.connect(self.broadcastConfigUpdate)
    
    def setWebSocketServer(self, websocket_server):
        """Set the WebSocket server reference"""
        self.websocket_server = websocket_server
    
    def setConfig(self, config):
        self.config = config
        self.createConfigForm()
        
    def createConfigForm(self):
        """Create form fields for all configuration settings"""
        # Clear existing widgets
        self.config_widgets = {}
        
        # Get form layout
        form_layout = self.form_group.layout()
        
        # Clear form layout
        while form_layout.count():
            item = form_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not self.config:
            self.statusLabel.setText("No configuration loaded")
            return
        
        # Create inputs for each config item
        for key, value in self.config.items():
            label = QLabel(f"{key}:")
            
            # Determine the appropriate widget type based on the value
            if key in ["folder_path", "steam_cmd_path"]:
                # Path inputs with browse button
                widget = PathLineEdit("dir", self.validatePath)
                widget.setText(value)
                widget.validationChanged.connect(lambda valid, k=key: self.onValidationChanged(valid, k))
                
            elif key == "mods":
                # Mod list - special handling
                widget = QLineEdit(value)
                widget.setToolTip("Comma-separated list of mod IDs")
                widget.textChanged.connect(lambda text, k=key: self.onFieldChanged(text, k))
                
            elif isinstance(value, int):
                # Numeric inputs
                widget = QSpinBox()
                widget.setMinimum(0)
                widget.setMaximum(99999)
                widget.setValue(value)
                widget.valueChanged.connect(lambda val, k=key: self.onFieldChanged(val, k))
                
            elif isinstance(value, bool):
                # Boolean inputs
                widget = QCheckBox()
                widget.setChecked(value)
                widget.stateChanged.connect(lambda state, k=key: self.onFieldChanged(bool(state), k))
                
            else:
                # Default to text input
                widget = QLineEdit(str(value))
                widget.textChanged.connect(lambda text, k=key: self.onFieldChanged(text, k))
            
            form_layout.addRow(label, widget)
            self.config_widgets[key] = widget
        
        self.statusLabel.setText("Configuration loaded successfully")
        logger.info("Configuration form created successfully")
        
        # Broadcast configuration
        self.configUpdated.emit(self.getConfigData())
    
    def validatePath(self, path):
        """Validate a path input"""
        if not path:
            return True, ""  # Empty is allowed
            
        if os.path.exists(path):
            return True, ""
        else:
            return False, f"Path does not exist: {path}"
    
    def getConfigData(self):
        """Get configuration data for WebSocket broadcasts"""
        # Create a clean copy of the configuration
        config_data = dict(self.config)
        
        # Remove any sensitive information
        if 'auth_key' in config_data:
            config_data['auth_key'] = '***HIDDEN***'
        
        return {
            'config': config_data,
            'valid': self.valid
        }
    
    def onFieldChanged(self, value, key):
        """Handle field value changes"""
        # Update the in-memory config
        self.config[key] = value
    
    def onValidationChanged(self, valid, key):
        """Handle validation state changes"""
        # Update overall validation state
        self.valid = all(widget.valid for widget in self.config_widgets.values() 
                         if hasattr(widget, 'valid'))
        
        # Update save button state
        self.saveButton.setEnabled(self.valid)
        
        if not valid:
            logger.warning(f"Validation failed for {key}")
    
    def onSaveClicked(self):
        """Handle save button click"""
        if not self.valid:
            QMessageBox.warning(
                self,
                "Validation Error",
                "Please correct validation errors before saving."
            )
            return
        
        try:
            # Create backup of current config
            self.backupConfig()
            
            # Save to config.json
            with open('config.json', 'w') as file:
                json.dump(self.config, file, indent=4)
            
            self.statusLabel.setText("Configuration saved successfully")
            logger.info("Configuration saved successfully")
            
            # Broadcast configuration update
            self.configUpdated.emit(self.getConfigData())
            
            QMessageBox.information(
                self,
                "Configuration Saved",
                "Configuration has been saved successfully.\n"
                "Some changes may require a server restart to take effect."
            )
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            QMessageBox.critical(
                self,
                "Error Saving Configuration",
                f"Could not save configuration: {str(e)}"
            )
    
    def onResetClicked(self):
        """Handle reset button click"""
        confirm = QMessageBox.question(
            self,
            "Confirm Reset",
            "Are you sure you want to reset all configuration changes?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            # Reload from original config
            with open('config.json', 'r') as file:
                self.config = json.load(file)
            
            # Update UI with loaded config
            self.createConfigForm()
            
            
            self.statusLabel.setText("Configuration reset to original values")
            logger.info("Configuration reset to original values")
            
            # Broadcast configuration update
            self.configUpdated.emit(self.getConfigData())
    def onBackupClicked(self):
        """Handle backup button click"""
        try:
            backup_file = self.backupConfig()
            if backup_file:
                QMessageBox.information(
                    self,
                    "Backup Created",
                    f"Configuration backup created successfully:\n{backup_file}"
                )
            else:
                QMessageBox.warning(
                    self,
                    "Backup Not Created",
                    "No configuration file found to backup."
                )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Backup Error",
                f"Error creating backup: {str(e)}"
            )
    
    def onBrowseConfigClicked(self):
        """Handle browse config file button click"""
        try:
            # Open the folder containing config.json
            os.startfile(os.path.dirname(os.path.abspath('config.json')))
        except Exception as e:
            logger.error(f"Error opening config folder: {e}")
            QMessageBox.critical(
                self,
                "Error Opening Folder",
                f"Could not open configuration folder: {str(e)}"
            )
    
    def backupConfig(self):
        """Create a backup of the current config file"""
        try:
            source = 'config.json'
            if not os.path.exists(source):
                return None
                
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = 'config_backups'
            
            # Create backup directory if it doesn't exist
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
            
            # Create backup with timestamp
            backup_file = os.path.join(backup_dir, f'config_{timestamp}.json')
            shutil.copy2(source, backup_file)
            
            logger.info(f"Created configuration backup: {backup_file}")
            return backup_file
            return backup_file
        except Exception as e:
            logger.error(f"Error creating configuration backup: {e}")
            raise  # Re-raise the exception to be handled by the caller
    
    def broadcastConfigUpdate(self, config_data):
        """Broadcast configuration update to all WebSocket clients"""
        if hasattr(self, 'websocket_server') and self.websocket_server and self.websocket_server.is_running:
            self.websocket_server.broadcast_event("status", "config_update", config_data)
    
    def updateFromStatusMessage(self, message_data):
        """Update configuration from a WebSocket status message"""
        try:
            if 'config' in message_data and isinstance(message_data['config'], dict):
                # Don't update configuration automatically, just notify the user
                # that there are configuration changes available
                QMessageBox.information(
                    self,
                    "Configuration Update",
                    "New configuration settings are available from a remote client. "
                    "Would you like to review and apply these changes?",
                    QMessageBox.Yes | QMessageBox.No
                )
                
                # If the user wants to apply the changes, show them in the UI
                # (but don't save them yet)
                if QMessageBox.Yes:
                    temp_config = dict(self.config)
                    temp_config.update(message_data['config'])
                    
                    # Create a temporary backup of the current configuration
                    self.backupConfig()
                    
                    # Update the UI with the new configuration
                    self.config = temp_config
                    self.createConfigForm()
                    
                    self.statusLabel.setText("Remote configuration loaded - review and save to apply")
        except Exception as e:
            logger.error(f"Error handling WebSocket configuration update: {e}")
    
    def handleWebSocketCommand(self, command, data):
        """Handle commands received from WebSocket clients"""
        try:
            if command == "get_config":
                # Return current configuration
                return True, self.getConfigData()
            
            elif command == "update_config":
                if 'config' in data and isinstance(data['config'], dict):
                    # Create a backup before updating
                    self.backupConfig()
                    
                    # Update local configuration (only valid keys)
                    updated_keys = []
                    for key, value in data['config'].items():
                        if key in self.config:
                            # Don't update sensitive information
                            if key not in ['auth_key']:
                                self.config[key] = value
                                updated_keys.append(key)
                    
                    # Save the updated configuration
                    with open('config.json', 'w') as file:
                        json.dump(self.config, file, indent=4)
                    
                    # Update UI
                    self.createConfigForm()
                    
                    return True, {
                        "message": "Configuration updated successfully",
                        "updated_keys": updated_keys
                    }
                return False, "Invalid configuration data"
            
            elif command == "backup_config":
                # Create a backup of the current configuration
                backup_file = self.backupConfig()
                if backup_file:
                    return True, {"backup_file": backup_file}
                return False, "Failed to create backup"
            
            return False, f"Unknown command: {command}"
        except Exception as e:
            logger.error(f"Error handling WebSocket command {command}: {e}")
            return False, f"Error: {str(e)}"

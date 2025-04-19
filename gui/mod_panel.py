import os
import json
import logging
import threading
import webbrowser
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QGroupBox, 
    QTableWidget, QTableWidgetItem, QHeaderView,
    QLineEdit, QMessageBox, QInputDialog, QAbstractItemView
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QColor, QBrush

# Import existing mod_checker functionality
from mod_checker import add_new_mod_ids, read_json, update_mods_info
import LastOasisManager

logger = logging.getLogger('LOManagerGUI.ModPanel')

class ModPanel(QWidget):
    """Panel for mod management"""
    
    # Constants
    TOTAL_COLUMNS = 5
    
    # Signal to broadcast mod status updates
    statusUpdated = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        """Initialize the mod panel"""
        super().__init__(parent)
        self.config = {}
        self.mods_info = {}
        self.websocket_server = None
        self.initUI()
    
    def initUI(self):
        """Initialize the user interface"""
        main_layout = QVBoxLayout()
        
        # Controls for mod management
        control_group = QGroupBox("Mod Controls")
        control_layout = QHBoxLayout()
        
        self.addModButton = QPushButton("Add Mod")
        self.removeModButton = QPushButton("Remove Selected Mod")
        self.checkUpdatesButton = QPushButton("Check for Updates")
        self.updateModsButton = QPushButton("Update Mods")
        self.viewOnSteamButton = QPushButton("View on Steam Workshop")
        
        # Connect signals
        self.addModButton.clicked.connect(self.onAddModClicked)
        self.removeModButton.clicked.connect(self.onRemoveModClicked)
        self.checkUpdatesButton.clicked.connect(self.onCheckUpdatesClicked)
        self.updateModsButton.clicked.connect(self.onUpdateModsClicked)
        self.viewOnSteamButton.clicked.connect(self.onViewOnSteamClicked)
        
        control_layout.addWidget(self.addModButton)
        control_layout.addWidget(self.removeModButton)
        control_layout.addWidget(self.checkUpdatesButton)
        control_layout.addWidget(self.updateModsButton)
        control_layout.addWidget(self.viewOnSteamButton)
        
        control_group.setLayout(control_layout)
        main_layout.addWidget(control_group)
        
        # Mod list table
        self.modTable = QTableWidget(0, self.TOTAL_COLUMNS)  # Rows will be added dynamically
        self.modTable.setHorizontalHeaderLabels(["Mod ID", "Name", "Version", "Status", "Last Updated"])
        self.modTable.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.modTable.setSelectionMode(QAbstractItemView.SingleSelection)
        self.modTable.setEditTriggers(QAbstractItemView.NoEditTriggers)
        
        # Set column widths
        header = self.modTable.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        
        main_layout.addWidget(self.modTable)
        
        # Status message
        self.statusLabel = QLabel("No mods loaded")
        main_layout.addWidget(self.statusLabel)
        
        # Set up timer for status updates
        self.timer = QTimer()
        self.timer.timeout.connect(self.checkModUpdates)
        self.timer.start(60000)  # Check every minute
        self.timer.start(60000)  # Check every minute
        
        self.setLayout(main_layout)
        
        # Connect the status updated signal to broadcast method
        self.statusUpdated.connect(self.broadcastModStatus)
    
    def setWebSocketServer(self, websocket_server):
        """Set the WebSocket server reference"""
        self.websocket_server = websocket_server
    
    def setConfig(self, config):
        self.config = config
        self.loadModsInfo()
    
    def parse_mod_info(self, mod_info_str):
        """
        Parse the mod info string into component parts
        Expected format: "size\ncreation date\nupdate date"
        """
        result = {
            'size': 'Unknown',
            'creation_date': 'Unknown',
            'update_date': 'Unknown'
        }
        
        if mod_info_str:
            try:
                parts = mod_info_str.split('\n')
                if len(parts) >= 1:
                    result['size'] = parts[0]
                if len(parts) >= 2:
                    result['creation_date'] = parts[1]
                if len(parts) >= 3:
                    result['update_date'] = parts[2]
                # Check for status part
                if len(parts) >= 4:
                    result['status'] = parts[3]
            except Exception as e:
                logger.warning(f"Error parsing mod info string: {e}")
        
        return result
    
    def loadModsInfo(self):
        """Load mod information from mods_info.json"""
        try:
            # Clear existing table
            self.modTable.setRowCount(0)
            
            # Load mods from config
            if not self.config or 'mods' not in self.config:
                self.statusLabel.setText("No mods configured")
                return
                
            mod_ids = self.config['mods'].split(',')
            self.mods_info = read_json('mods_info.json')
            
            # Update table
            for i, mod_id in enumerate(mod_ids):
                mod_info_str = self.mods_info.get(mod_id, "")
                
                # Default values
                name = f'Mod {mod_id}'
                version = 'Unknown'
                last_update = 'Unknown'
                needs_update = False
                
                # Parse the string information from mod_info_str if available
                if mod_info_str:
                    mod_info = self.parse_mod_info(mod_info_str)
                    version = mod_info['size']  # Use size as version display
                    last_update = mod_info['update_date']
                    
                    # For name, just use the mod ID for now
                    # In future could fetch actual name from Steam
                
                # Add a new row
                self.modTable.insertRow(i)
                
                # Set cell values
                id_item = QTableWidgetItem(mod_id)
                name_item = QTableWidgetItem(name)
                version_item = QTableWidgetItem(str(version))
                
                # For now, just display "Up to Date" since we don't have a way
                # to determine if updates are needed from the string format
                status = "Up to Date"
                status_item = QTableWidgetItem(status)
                status_item.setForeground(QBrush(QColor("green")))
                
                # Add last update item
                last_update_item = QTableWidgetItem(last_update)
                
                # Add items to row
                self.modTable.setItem(i, 0, id_item)
                self.modTable.setItem(i, 1, name_item)
                self.modTable.setItem(i, 2, version_item)
                self.modTable.setItem(i, 3, status_item)
                self.modTable.setItem(i, 4, last_update_item)
            
            self.statusLabel.setText(f"{len(mod_ids)} mods loaded")
            
            # Broadcast mod status to WebSocket clients
            self.statusUpdated.emit(self.getModStatusData())
        except Exception as e:
            logger.error(f"Error loading mods: {e}")
            self.statusLabel.setText(f"Error loading mods: {str(e)}")
    
    def getModStatusData(self):
        """Get mod status data for WebSocket broadcasts"""
        mods_data = []
        outdated_count = 0
        up_to_date_count = 0
        
        # Get number of rows in the table
        rows = self.modTable.rowCount()
        
        for i in range(rows):
            mod_id = self.modTable.item(i, 0).text()
            name = self.modTable.item(i, 1).text()
            version = self.modTable.item(i, 2).text()
            status = self.modTable.item(i, 3).text()
            last_update = self.modTable.item(i, 4).text()
            
            mods_data.append({
                'mod_id': mod_id,
                'name': name,
                'version': version,
                'status': status,
                'last_update': last_update
            })
            
            # Count mods by status
            if status.lower() == "needs update":
                outdated_count += 1
            elif status.lower() == "up to date":
                up_to_date_count += 1
        
        return {
            'mods': mods_data,
            'summary': {
                'total': rows,
                'outdated': outdated_count,
                'up_to_date': up_to_date_count
            }
        }
            
    def saveModsConfig(self, mod_list):
        """Save the current mod list to config"""
        try:
            self.config['mods'] = ','.join(mod_list)
            with open('config.json', 'w') as f:
                json.dump(self.config, f, indent=4)
            logger.info("Saved mod configuration")
            
            # Broadcast update
            self.statusUpdated.emit(self.getModStatusData())
            return True
        except Exception as e:
            logger.error(f"Error saving mod configuration: {e}")
            QMessageBox.critical(
                self,
                "Error Saving Configuration",
                f"Could not save mod configuration: {str(e)}"
            )
            return False

    def onAddModClicked(self):
        """Handle add mod button click"""
        mod_id, ok = QInputDialog.getText(
            self,
            "Add Mod",
            "Enter the Steam Workshop ID of the mod:"
        )
        
        if ok and mod_id:
            try:
                # Validate mod_id is numeric
                int(mod_id)  # This will raise ValueError if not numeric
                
                # Add to current mod list
                current_mods = []
                if 'mods' in self.config:
                    current_mods = self.config['mods'].split(',')
                
                if mod_id in current_mods:
                    QMessageBox.warning(
                        self,
                        "Duplicate Mod",
                        f"Mod {mod_id} is already in the mod list."
                    )
                    return
                
                current_mods.append(mod_id)
                
                # Save updated mod list
                if self.saveModsConfig(current_mods):
                    try:
                        # Read fresh mods_info from file
                        fresh_mods_info = read_json('mods_info.json')
                        
                        # Add to mods_info.json using the add_new_mod_ids function
                        updated_mods_info = add_new_mod_ids(fresh_mods_info, [mod_id])
                        
                        # Write updated info back to file
                        with open('mods_info.json', 'w') as f:
                            json.dump(updated_mods_info, f, indent=4)
                            
                        # Update our instance variable
                        self.mods_info = updated_mods_info
                    except Exception as e:
                        logger.error(f"Error updating mods_info.json: {e}")
                        QMessageBox.warning(
                            self,
                            "Warning",
                            f"Mod added to config, but mods_info.json could not be updated: {str(e)}"
                        )
                    
                    # Reload mods info and update UI
                    self.loadModsInfo()
                    
                    # Broadcast updated mod status
                    self.statusUpdated.emit(self.getModStatusData())
                    
                    QMessageBox.information(
                        self,
                        "Mod Added",
                        f"Mod {mod_id} has been added to the mod list."
                    )
            except ValueError:
                QMessageBox.critical(
                    self,
                    "Invalid Mod ID",
                    "The mod ID must be a numeric value."
                )
            except Exception as e:
                logger.error(f"Error adding mod: {e}")
                QMessageBox.critical(
                    self,
                    "Error Adding Mod",
                    f"Could not add mod: {str(e)}"
                )

    def onRemoveModClicked(self):
        """Handle remove mod button click"""
        selected_row = self.modTable.currentRow()
        if selected_row >= 0:
            mod_id_item = self.modTable.item(selected_row, 0)
            mod_id = mod_id_item.text()
            
            confirm = QMessageBox.question(
                self,
                "Confirm Removal",
                f"Are you sure you want to remove mod {mod_id}?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if confirm == QMessageBox.Yes:
                try:
                    # Remove from current mod list
                    current_mods = []
                    if 'mods' in self.config:
                        current_mods = self.config['mods'].split(',')
                    
                    if mod_id in current_mods:
                        current_mods.remove(mod_id)
                    
                    # Save updated mod list
                    if self.saveModsConfig(current_mods):
                        # Reload mods info and update UI
                        self.loadModsInfo()
                        
                        QMessageBox.information(
                            self,
                            "Mod Removed",
                            f"Mod {mod_id} has been removed from the mod list."
                        )
                except Exception as e:
                    logger.error(f"Error removing mod: {e}")
                    QMessageBox.critical(
                        self,
                        "Error Removing Mod",
                        f"Could not remove mod: {str(e)}"
                    )
        else:
            QMessageBox.warning(
                self,
                "No Selection",
                "Please select a mod to remove."
            )

    def onCheckUpdatesClicked(self):
        """Handle check for updates button click"""
        thread = threading.Thread(target=self._checkUpdatesThread)
        thread.daemon = True
        thread.start()

    def _checkUpdatesThread(self):
        """Background thread for checking updates"""
        try:
            # Make sure self.mods_info is a dictionary before passing
            if not isinstance(self.mods_info, dict):
                self.mods_info = {}
                
            # Get mod IDs from config and filter out empty strings
            mods_config = self.config.get("mods", "")
            if not mods_config:
                logger.warning("No mods configured to check for updates")
                return
                
            # Split by comma and filter out empty strings
            mod_ids = [mod_id.strip() for mod_id in mods_config.split(",") if mod_id.strip()]
            
            if not mod_ids:
                logger.warning("No valid mod IDs found in config to check for updates")
                return
                
            logger.info(f"Checking updates for {len(mod_ids)} mods: {', '.join(mod_ids)}")
                
            out_of_date, self.mods_info = update_mods_info(
                self.mods_info,
                mod_ids
            )
            
            # Save updated mod info back to file
            with open('mods_info.json', 'w') as f:
                json.dump(self.mods_info, f, indent=4)
                
            if out_of_date:
                self.loadModsInfo()  # Refresh the UI
                logger.info(f"Found {len(out_of_date)} mods that need updates")
                # Broadcast updated mod status
                self.statusUpdated.emit(self.getModStatusData())
            else:
                logger.info("All mods are up to date")
                # Still broadcast status update
                self.statusUpdated.emit(self.getModStatusData())
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")

    def onUpdateModsClicked(self):
        """Handle update mods button click"""
        confirm = QMessageBox.question(
            self,
            "Confirm Update",
            "This will restart all servers to update mods. Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            LastOasisManager.restart_all_tiles(1)
            self.loadModsInfo()  # Refresh the UI after update
            # Broadcast updated mod status
            self.statusUpdated.emit(self.getModStatusData())

    def onViewOnSteamClicked(self):
        """Handle view on Steam button click"""
        selected_row = self.modTable.currentRow()
        if selected_row >= 0:
            mod_id_item = self.modTable.item(selected_row, 0)
            mod_id = mod_id_item.text()
            
            # Open Steam Workshop page for the mod
            url = f"https://steamcommunity.com/sharedfiles/filedetails/?id={mod_id}"
            webbrowser.open(url)
            logger.info(f"Opening Steam Workshop page for mod {mod_id}")
        else:
            QMessageBox.warning(
                self,
                "No Selection",
                "Please select a mod to view on Steam Workshop."
            )

    def checkModUpdates(self):
        """Periodic check for mod updates"""
        if self.config and 'mods' in self.config:
            thread = threading.Thread(target=self._checkUpdatesThread)
            thread.daemon = True
            thread.start()
    
    def broadcastModStatus(self, status_data):
        """Broadcast mod status to all WebSocket clients"""
        if hasattr(self, 'websocket_server') and self.websocket_server and self.websocket_server.is_running:
            self.websocket_server.broadcast_event("status", "mod_status", status_data)
    
    def updateFromStatusMessage(self, message_data):
        """Update mod status from a WebSocket status message"""
        try:
            # Check if we have mods data
            if 'mods' in message_data:
                # For now, just reload the mods info from file
                # This could be enhanced to directly update the UI from message data
                self.loadModsInfo()
                
                # Update summary if available
                if 'summary' in message_data:
                    summary = message_data['summary']
                    total = summary.get('total', 0)
                    outdated = summary.get('outdated', 0)
                    self.statusLabel.setText(f"{total} mods loaded, {outdated} need updates")
        except Exception as e:
            logger.error(f"Error updating from WebSocket status message: {e}")
    
    def handleWebSocketCommand(self, command, data):
        """Handle commands received from WebSocket clients"""
        try:
            if command == "add_mod":
                mod_id = data.get("mod_id")
                if mod_id:
                    # Add to current mod list
                    current_mods = []
                    if 'mods' in self.config:
                        current_mods = self.config['mods'].split(',')
                    
                    if mod_id not in current_mods:
                        current_mods.append(mod_id)
                        if self.saveModsConfig(current_mods):
                            # Update mods_info.json
                            fresh_mods_info = read_json('mods_info.json')
                            updated_mods_info = add_new_mod_ids(fresh_mods_info, [mod_id])
                            with open('mods_info.json', 'w') as f:
                                json.dump(updated_mods_info, f, indent=4)
                            self.mods_info = updated_mods_info
                            self.loadModsInfo()
                            return True, f"Mod {mod_id} added successfully"
                    else:
                        return False, f"Mod {mod_id} is already in the mod list"
            
            elif command == "remove_mod":
                mod_id = data.get("mod_id")
                if mod_id:
                    # Remove from current mod list
                    current_mods = []
                    if 'mods' in self.config:
                        current_mods = self.config['mods'].split(',')
                    
                    if mod_id in current_mods:
                        current_mods.remove(mod_id)
                        if self.saveModsConfig(current_mods):
                            self.loadModsInfo()
                            return True, f"Mod {mod_id} removed successfully"
                    else:
                        return False, f"Mod {mod_id} is not in the mod list"
            
            elif command == "check_updates":
                # Start update check in background
                thread = threading.Thread(target=self._checkUpdatesThread)
                thread.daemon = True
                thread.start()
                return True, "Update check started"
            
            elif command == "update_mods":
                LastOasisManager.restart_all_tiles(1)
                self.loadModsInfo()
                return True, "Mods update started, servers restarting"
            
            return False, f"Unknown command: {command}"
        except Exception as e:
            logger.error(f"Error handling WebSocket command {command}: {e}")
            return False, f"Error: {str(e)}"

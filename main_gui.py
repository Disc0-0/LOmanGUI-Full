import sys
import json
import os
import logging
import traceback
import warnings
import config_utils  # Import the configuration utilities module

# Filter out the specific sipPyTypeDict() deprecation warning
warnings.filterwarnings("ignore", message=r"sipPyTypeDict\(\) is deprecated")

# Import WebSocket server
from websocket_server import WebSocketServer, WebSocketMessage
# Import PyQt5 modules
from PyQt5 import sip

# Import PyQt5 modules
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QVBoxLayout, 
    QWidget, QMenuBar, QMenu, QAction, QMessageBox, 
    QStatusBar, QLabel
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon, QFont, QPixmap
from PyQt5 import QtGui

# Import custom panels
from gui.server_panel import ServerPanel
from gui.mod_panel import ModPanel
from gui.config_panel import ConfigPanel
from gui.log_panel import LogPanel
from gui.admin_panel import AdminPanel
from gui.discord_panel import DiscordPanel

# Import existing functionality
import LastOasisManager
import admin_writer
from mod_checker import add_new_mod_ids, read_json, update_mods_info

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='lomangui.log',
    filemode='a'
)
logger = logging.getLogger('LOManagerGUI')

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = {}
        self.websocket_server = None
        self.initUI()
        self.loadConfig()
        self.initWebSocket()
        
    def initUI(self):
        """Initialize the user interface"""
        self.setWindowTitle("Last Oasis Manager GUI")
        self.setGeometry(100, 100, 1200, 800)
        
        # Set application icon - create a simple icon if one doesn't exist
        self.setWindowIcon(QIcon(self.createAppIcon()))
        
        # Apply stylesheet
        self.setStyleSheet(self.getStyleSheet())
        
        # Create central widget and layout
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(15, 15, 15, 15)  # Add margin around the entire layout
        layout.setSpacing(10)  # Add spacing between widgets
        # Create tab widget
        # Create header label with title
        header_label = QLabel("Last Oasis Server Manager")
        header_label.setObjectName("headerLabel")
        header_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(header_label)
        
        # Create tab widget
        self.tabs = QTabWidget()
        self.tabs.setObjectName("mainTabs")
        # Add tabs for each panel
        self.server_panel = ServerPanel()
        self.mod_panel = ModPanel()
        self.config_panel = ConfigPanel()
        self.log_panel = LogPanel()
        self.admin_panel = AdminPanel()
        self.discord_panel = DiscordPanel()
        
        self.tabs.addTab(self.server_panel, "Server Management")
        self.tabs.addTab(self.mod_panel, "Mod Management")
        self.tabs.addTab(self.config_panel, "Configuration")
        self.tabs.addTab(self.log_panel, "Logs")
        self.tabs.addTab(self.admin_panel, "Admin Messages")
        self.tabs.addTab(self.discord_panel, "Discord Output")
        
        layout.addWidget(self.tabs)
        
        # Create menu bar
        self.createMenus()
        
        # Create status bar
        # Create status bar
        self.statusBar = QStatusBar()
        self.statusBar.setObjectName("statusBar")
        self.setStatusBar(self.statusBar)
        self.statusMsg = QLabel("Ready")
        self.statusMsg.setObjectName("statusMsg")
        self.statusBar.addWidget(self.statusMsg)
        self.statusBar.setFixedHeight(30)  # Set a fixed height for the status bar
        # Set up timer for status updates
        self.timer = QTimer()
        self.timer.timeout.connect(self.updateStatus)
        self.timer.start(5000)  # Update every 5 seconds
    
    def createMenus(self):
        """Create application menus"""
        # File menu
        fileMenu = self.menuBar().addMenu("&File")
        
        # Reload Config action
        reloadConfigAction = QAction("Reload &Configuration", self)
        reloadConfigAction.setShortcut("Ctrl+R")
        reloadConfigAction.triggered.connect(self.loadConfig)
        fileMenu.addAction(reloadConfigAction)
        
        # Exit action
        exitAction = QAction("E&xit", self)
        exitAction.setShortcut("Ctrl+Q")
        exitAction.triggered.connect(self.close)
        fileMenu.addAction(exitAction)
        
        # Help menu
        helpMenu = self.menuBar().addMenu("&Help")
        
        # About action
        aboutAction = QAction("&About", self)
        aboutAction.triggered.connect(self.showAbout)
        helpMenu.addAction(aboutAction)
    
    def loadConfig(self):
        """Load configuration from config.json using config_utils to handle BOM"""
        try:
            # Use config_utils to safely load the configuration
            config_path = os.path.abspath("config.json")
            loaded_config, success, error = config_utils.load_config_safely(config_path)
            
            if not success:
                raise Exception(f"Failed to load configuration: {error}")
                
            self.config = loaded_config
            
            # Initialize LastOasisManager with the config
            LastOasisManager.update_config()
            # Initialize TileTracker
            log_folder = os.path.join(self.config["folder_path"].replace("Binaries\\Win64\\", ""), "Saved\\Logs")
            LastOasisManager.tile_tracker = LastOasisManager.get_tracker(
                log_folder=log_folder,
                config_path="config.json"
            )
            
            # Pass config to panels
            self.server_panel.setConfig(self.config)
            self.mod_panel.setConfig(self.config)
            self.config_panel.setConfig(self.config)
            self.log_panel.setConfig(self.config)
            self.admin_panel.setConfig(self.config)
            self.discord_panel.setConfig(self.config)
            
            self.statusMsg.setText("Configuration loaded successfully")
            logger.info("Configuration loaded successfully")
        except Exception as e:
            self.showError("Error loading configuration", str(e))
            logger.error(f"Error loading configuration: {e}")
    
    def updateStatus(self):
        """Update status information periodically"""
        # Show WebSocket server status
        if hasattr(self, 'websocket_server') and self.websocket_server:
            if self.websocket_server.is_running:
                connected_clients = len(self.websocket_server.clients)
                self.statusMsg.setText(f"WebSocket server running - {connected_clients} client(s) connected")
            else:
                self.statusMsg.setText("WebSocket server not running")
        else:
            self.statusMsg.setText("WebSocket server not initialized")
    
    def showAbout(self):
        """Show about dialog"""
        QMessageBox.about(
            self, 
            "About Last Oasis Manager GUI",
            "Last Oasis Manager GUI\n\n"
            "The premier solution for managing your Last Oasis dedicated servers "
            "with ease and precision. Navigate the vast dunes of server administration "
            "without getting lost in the technical sandstorm.\n\n"
            "Features:\n"
            "• Intuitive server tile management and monitoring\n"
            "• Streamlined mod installation and updates\n"
            "• Automated server updates via SteamCMD\n"
            "• Real-time log monitoring and analysis\n"
            "• Administrative message broadcasting\n\n"
            "DISCLAIMER: This software is provided 'as is', without warranty of any kind. "
            "Use at your own risk. While designed to enhance your server management experience, "
            "please back up important data before use.\n\n"
            "Made with ♥ by Disc0 © 2025\n"
            "Last Oasis is a trademark of Donkey Crew. This tool is not affiliated with or endorsed by Donkey Crew."
        )
    
    def showError(self, title, message):
        """Show error dialog"""
        QMessageBox.critical(self, title, message)
    
    def closeEvent(self, event):
        """Handle application close event"""
        reply = QMessageBox.question(
            self, 'Confirm Exit',
            "Are you sure you want to exit? This will not stop any running servers.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Stop the WebSocket server
            if self.websocket_server and self.websocket_server.is_running:
                logger.info("Stopping WebSocket server...")
                self.websocket_server.stop()
                
            # Clean up resources before exit
            event.accept()
        else:
            event.ignore()

    def getStyleSheet(self):
        """Return the application stylesheet"""
        return """
            QMainWindow {
                background-color: #f5f5f5;
            }
            QTabWidget::pane {
                border: 1px solid #cccccc;
                background-color: white;
                border-radius: 4px;
            }
            QTabBar::tab {
                background-color: #e0e0e0;
                color: #505050;
                min-width: 8ex;
                min-height: 3ex;
                padding: 8px 15px;
                border: 1px solid #cccccc;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: white;
                color: #303030;
                border-bottom-color: white;
                font-weight: bold;
            }
            QTabBar::tab:hover:!selected {
                background-color: #e8e8e8;
            }
            QStatusBar {
                background-color: #3a6ea5;
                color: white;
            }
            QLabel#statusMsg {
                color: white;
                padding-left: 10px;
                font-weight: bold;
            }
            QPushButton {
                background-color: #4a86c5;
                color: white;
                border: none;
                padding: 8px 15px;
                min-width: 100px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #5a96d5;
            }
            QPushButton:pressed {
                background-color: #3a76b5;
            }
            QLabel#headerLabel {
                font-size: 20px;
                font-weight: bold;
                color: #3a6ea5;
                margin-bottom: 10px;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #cccccc;
                border-radius: 4px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 5px;
                color: #3a6ea5;
            }
            QTableWidget {
                alternate-background-color: #f9f9f9;
                selection-background-color: #c2d8e9;
                selection-color: #000000;
                border: 1px solid #cccccc;
                border-radius: 4px;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QHeaderView::section {
                background-color: #e0e0e0;
                padding: 5px;
                border: 1px solid #cccccc;
                font-weight: bold;
            }
            QLineEdit, QComboBox {
                padding: 5px;
                border: 1px solid #cccccc;
                border-radius: 3px;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #4a86c5;
            }
            QMenu {
                background-color: white;
                border: 1px solid #cccccc;
            }
            QMenu::item {
                padding: 5px 20px 5px 20px;
            }
            QMenu::item:selected {
                background-color: #c2d8e9;
            }
            QMenuBar {
                background-color: #f0f0f0;
                border-bottom: 1px solid #cccccc;
            }
            QMenuBar::item {
                padding: 6px 10px;
                background-color: transparent;
            }
            QMenuBar::item:selected {
                background-color: #c2d8e9;
                border-radius:.px;
            }
        """

    def createAppIcon(self):
        """Create a simple application icon if one doesn't exist"""
        # Create a 64x64 icon with 'LO' text
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # Draw background circle
        painter.setBrush(QtGui.QBrush(QtGui.QColor("#3a6ea5")))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(2, 2, 60, 60)
        
        # Draw text
        painter.setPen(QtGui.QPen(QtGui.QColor("white")))
        font = QFont("Arial", 20, QFont.Bold)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "LO")
        
        return pixmap

    def initWebSocket(self):
        """Initialize and start the WebSocket server"""
        try:
            # Get host and port from config, or use default values
            host = self.config.get('websocket_host', 'localhost')
            port = self.config.get('websocket_port', 8765)
            auth_key = self.config.get('websocket_auth_key', None)
            
            # Create and start the WebSocket server
            self.websocket_server = WebSocketServer(host=host, port=port, auth_key=auth_key)
            
            # Connect signals to handle WebSocket events
            self.websocket_server.client_connected.connect(self.onClientConnected)
            self.websocket_server.client_disconnected.connect(self.onClientDisconnected)
            self.websocket_server.message_received.connect(self.onMessageReceived)
            self.websocket_server.server_status_changed.connect(self.onServerStatusChanged)
            
            # Start the server
            success = self.websocket_server.start()
            if success:
                logger.info(f"WebSocket server started on {host}:{port}")
                self.statusMsg.setText(f"WebSocket server running on {host}:{port}")
            else:
                logger.error("Failed to start WebSocket server")
                self.statusMsg.setText("Failed to start WebSocket server")
        except Exception as e:
            logger.error(f"Error initializing WebSocket server: {e}")
            self.statusMsg.setText(f"WebSocket server error: {str(e)}")
            self.showError("WebSocket Server Error", str(e))
    
    def onClientConnected(self, client_id):
        """Handle client connection event"""
        logger.info(f"Client connected: {client_id}")
        # Update status information immediately
        self.updateStatus()
    
    def onClientDisconnected(self, client_id):
        """Handle client disconnection event"""
        logger.info(f"Client disconnected: {client_id}")
        # Update status information immediately
        self.updateStatus()
    
    def onMessageReceived(self, client_id, message_text):
        """Handle incoming WebSocket message"""
        logger.debug(f"Message from {client_id}: {message_text}")
        try:
            # Process message if needed
            message = WebSocketMessage.from_json(message_text)
            
            # If this is a GUI-relevant message, update the GUI
            if message.event_type == "status":
                # Update the appropriate panel based on the message action
                if message.action == "server_status":
                    self.server_panel.updateFromStatusMessage(message.data)
                elif message.action == "mod_status":
                    self.mod_panel.updateFromStatusMessage(message.data)
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}")
    
    def onServerStatusChanged(self, is_running):
        """Handle WebSocket server status change"""
        if is_running:
            logger.info("WebSocket server is now running")
            self.statusMsg.setText("WebSocket server is running")
        else:
            logger.info("WebSocket server has stopped")
            self.statusMsg.setText("WebSocket server has stopped")
    
    def broadcastEvent(self, event_type, action, data=None):
        """Send event to all connected WebSocket clients"""
        if self.websocket_server and self.websocket_server.is_running:
            self.websocket_server.broadcast_event(event_type, action, data)

def main():
    """Application entry point"""
    app = QApplication(sys.argv)
    # Set application-wide font
    app.setFont(QFont("Segoe UI", 9))
    window = MainWindow()
    window.show()
    
    try:
        sys.exit(app.exec_())
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}")
        logger.critical(traceback.format_exc())
        QMessageBox.critical(
            None,
            "Critical Error",
            f"An unhandled error occurred:\n\n{str(e)}\n\nSee logs for details."
        )


if __name__ == "__main__":
    main()




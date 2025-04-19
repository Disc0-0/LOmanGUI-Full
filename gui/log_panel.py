import os
import re
import time
import threading
import logging
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QComboBox, 
    QTextEdit, QCheckBox, QLineEdit,
    QGroupBox, QFileDialog, QMessageBox,
    QSplitter, QApplication
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt5.QtGui import QTextCursor, QColor, QTextCharFormat, QBrush

logger = logging.getLogger('LOManagerGUI.LogPanel')

class LogWatcher(QThread):
    """Watches log files for changes and emits signal when new content is available"""
    
    log_updated = pyqtSignal(str, str)  # filename, new content
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.log_files = {}  # filename -> last position
        self.running = True
        self.mutex = threading.Lock()
    
    def add_log_file(self, filename):
        """Add a log file to watch"""
        with self.mutex:
            if filename not in self.log_files:
                if os.path.exists(filename):
                    self.log_files[filename] = os.path.getsize(filename)
                else:
                    self.log_files[filename] = 0
    
    def remove_log_file(self, filename):
        """Remove a log file from the watch list"""
        with self.mutex:
            if filename in self.log_files:
                del self.log_files[filename]
    
    def run(self):
        """Thread main loop"""
        while self.running:
            with self.mutex:
                for filename in list(self.log_files.keys()):
                    if os.path.exists(filename):
                        current_size = os.path.getsize(filename)
                        last_size = self.log_files[filename]
                        
                        if current_size > last_size:
                            with open(filename, 'r', encoding='utf-8', errors='replace') as f:
                                f.seek(last_size)
                                new_content = f.read()
                                if new_content:
                                    self.log_updated.emit(filename, new_content)
                            
                            self.log_files[filename] = current_size
            
            time.sleep(0.5)  # Check every 500ms
    
    def stop(self):
        """Stop the watcher thread"""
        self.running = False

class LogPanel(QWidget):
    """Panel for log viewing and filtering"""
    
    LOG_LEVELS = {
        "ALL": -1,
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    
    # Signal for broadcasting log updates to WebSocket clients
    logUpdated = pyqtSignal(dict)
    filterChanged = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = {}
        self.log_files = []
        self.current_log = None
        self.filter_text = ""
        self.log_level = "ALL"
        self.auto_scroll = True
        self.websocket_server = None
        self.last_broadcast_time = 0
        self.log_buffer = []
        self.initUI()
        
        # Start log watcher
        self.log_watcher = LogWatcher()
        self.log_watcher.log_updated.connect(self.onLogUpdated)
        self.log_watcher.start()
    
    def initUI(self):
        """Initialize the UI components"""
        main_layout = QVBoxLayout()
        
        # Controls
        controls_layout = QHBoxLayout()
        
        # Log file selector
        self.log_selector = QComboBox()
        self.log_selector.currentIndexChanged.connect(self.onLogFileChanged)
        controls_layout.addWidget(QLabel("Log File:"))
        controls_layout.addWidget(self.log_selector)
        
        # Refresh button
        self.refreshButton = QPushButton("Refresh")
        self.refreshButton.clicked.connect(self.refreshLogs)
        controls_layout.addWidget(self.refreshButton)
        
        # Browse button
        self.browseButton = QPushButton("Browse...")
        self.browseButton.clicked.connect(self.browseLogFile)
        controls_layout.addWidget(self.browseButton)
        
        main_layout.addLayout(controls_layout)
        
        # Filtering and options
        filter_layout = QHBoxLayout()
        
        # Text filter
        filter_layout.addWidget(QLabel("Filter:"))
        self.filterEdit = QLineEdit()
        self.filterEdit.setPlaceholderText("Enter text to filter...")
        self.filterEdit.textChanged.connect(self.onFilterTextChanged)
        filter_layout.addWidget(self.filterEdit)
        
        # Log level filter
        filter_layout.addWidget(QLabel("Level:"))
        self.levelCombo = QComboBox()
        for level in self.LOG_LEVELS.keys():
            self.levelCombo.addItem(level)
        self.levelCombo.currentTextChanged.connect(self.onLogLevelChanged)
        filter_layout.addWidget(self.levelCombo)
        
        # Auto-scroll checkbox
        self.autoScrollCheck = QCheckBox("Auto-scroll")
        self.autoScrollCheck.setChecked(True)
        self.autoScrollCheck.stateChanged.connect(self.onAutoScrollChanged)
        filter_layout.addWidget(self.autoScrollCheck)
        
        # Clear button
        self.clearButton = QPushButton("Clear")
        self.clearButton.clicked.connect(self.clearLog)
        filter_layout.addWidget(self.clearButton)
        
        # Copy button
        self.copyButton = QPushButton("Copy to Clipboard")
        self.copyButton.clicked.connect(self.copyToClipboard)
        filter_layout.addWidget(self.copyButton)
        
        main_layout.addLayout(filter_layout)
        
        # Log text display
        self.logText = QTextEdit()
        self.logText.setReadOnly(True)
        self.logText.setLineWrapMode(QTextEdit.NoWrap)
        self.logText.setFont(QApplication.font("Monospace"))
        main_layout.addWidget(self.logText)
        
        # Status bar
        status_layout = QHBoxLayout()
        self.statusLabel = QLabel("No log file loaded")
        status_layout.addWidget(self.statusLabel)
        status_layout.addWidget(self.statusLabel)
        main_layout.addLayout(status_layout)
        self.setLayout(main_layout)
        
        # Connect signals for WebSocket communication
        self.logUpdated.connect(self.broadcastLogUpdate)
        self.filterChanged.connect(self.broadcastFilterUpdate)
        
        # Set up timer for periodic log refresh
        self.timer = QTimer()
        self.timer.timeout.connect(self.checkLogUpdates)
        self.timer.start(1000)  # Check every second
        
        # Set up timer for batched log broadcasting
        self.broadcast_timer = QTimer()
        self.broadcast_timer.timeout.connect(self.sendBufferedLogUpdates)
        self.broadcast_timer.start(2000)  # Broadcast every 2 seconds
    def setWebSocketServer(self, websocket_server):
        """Set the WebSocket server reference"""
        self.websocket_server = websocket_server
    
    def setConfig(self, config):
        """Set configuration and update UI accordingly"""
        self.config = config
        self.findLogFiles()
    
    def findLogFiles(self):
        """Find available log files based on configuration"""
        self.log_files = []
        
        # Default logs in the current directory
        if os.path.exists("loman.log"):
            self.log_files.append(os.path.abspath("loman.log"))
        
        if os.path.exists("lomangui.log"):
            self.log_files.append(os.path.abspath("lomangui.log"))
        
        # Game logs in configured directory
        if 'folder_path' in self.config:
            log_dir = self.config['folder_path'].replace("Binaries\\Win64\\", "Saved\\Logs")
            if os.path.exists(log_dir):
                for file in os.listdir(log_dir):
                    if file.lower().endswith('.log'):
                        self.log_files.append(os.path.join(log_dir, file))
        
        # Update log selector
        self.log_selector.clear()
        for log_file in self.log_files:
            self.log_selector.addItem(os.path.basename(log_file), log_file)
        
        # Select first log file if available
        if self.log_files:
            self.current_log = self.log_files[0]
            self.loadLogFile(self.current_log)
            self.log_watcher.add_log_file(self.current_log)
            
            # Broadcast available logs to WebSocket clients
            self.broadcastAvailableLogs()
    def loadLogFile(self, filename):
        """Load a log file into the display"""
        if not os.path.exists(filename):
            self.logText.clear()
            self.statusLabel.setText(f"Log file not found: {os.path.basename(filename)}")
            return
        
        try:
            with open(filename, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            self.logText.clear()
            self.applyContentFilter(content)
            
            file_size = os.path.getsize(filename)
            modified_time = datetime.fromtimestamp(os.path.getmtime(filename))
            self.statusLabel.setText(
                f"Log: {os.path.basename(filename)} | Size: {file_size / 1024:.1f} KB | "
                f"Last modified: {modified_time.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            # Update watcher
            self.log_watcher.add_log_file(filename)
            self.current_log = filename
            
        except Exception as e:
            logger.error(f"Error loading log file: {e}")
            self.logText.clear()
            self.statusLabel.setText(f"Error loading log file: {str(e)}")
    
    def applyContentFilter(self, content):
        """Apply filtering to log content and update display"""
        if not content:
            return
        
        # Split into lines for filtering
        lines = content.splitlines()
        filtered_lines = []
        
        for line in lines:
            # Apply text filter
            if self.filter_text and self.filter_text.lower() not in line.lower():
                continue
            
            # Apply log level filter
            if self.log_level != "ALL":
                level_match = False
                for level_name in self.LOG_LEVELS.keys():
                    if level_name != "ALL" and level_name in line:
                        level_val = self.LOG_LEVELS[level_name]
                        filter_val = self.LOG_LEVELS[self.log_level]
                        if level_val >= filter_val:
                            level_match = True
                            break
                if not level_match:
                    continue
            
            filtered_lines.append(line)
        
        # Format and add to text edit
        self.formatAndAddLines(filtered_lines)
    
    def formatAndAddLines(self, lines):
        """Format log lines with colors and add to text edit"""
        cursor = self.logText.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        for line in lines:
            fmt = QTextCharFormat()
            
            # Apply colors based on log level
            if "ERROR" in line or "CRITICAL" in line:
                fmt.setForeground(QBrush(QColor("red")))
            elif "WARNING" in line:
                fmt.setForeground(QBrush(QColor("orange")))
            elif "INFO" in line:
                fmt.setForeground(QBrush(QColor("blue")))
            elif "DEBUG" in line:
                fmt.setForeground(QBrush(QColor("gray")))
            
            # Apply highlight for filtered text
            if self.filter_text and self.filter_text.lower() in line.lower():
                fmt.setBackground(QBrush(QColor(255, 255, 0, 50)))  # Light yellow
            
            cursor.insertText(line + "\n", fmt)
        
        # Auto-scroll if enabled
        if self.auto_scroll:
            self.logText.setTextCursor(cursor)
            self.logText.ensureCursorVisible()
    
    def onLogFileChanged(self, index):
        """Handle log file selection change"""
        if index >= 0 and index < len(self.log_files):
            self.loadLogFile(self.log_files[index])
    
    def onFilterTextChanged(self, text):
        """Handle filter text change"""
        self.filter_text = text
        self.refreshLogs()
        
        # Broadcast filter change
        self.filterChanged.emit(self.getFilterData())
    
    def onLogLevelChanged(self, level):
        """Handle log level filter change"""
        self.log_level = level
        self.refreshLogs()
        
        # Broadcast filter change
        self.filterChanged.emit(self.getFilterData())
    def onAutoScrollChanged(self, state):
        """Handle auto-scroll checkbox change"""
        self.auto_scroll = (state == Qt.Checked)
        
        # Broadcast filter change
        self.filterChanged.emit(self.getFilterData())
    
    def refreshLogs(self):
        """Refresh log display"""
        if self.current_log:
            self.loadLogFile(self.current_log)
    
    def clearLog(self):
        """Clear log display"""
        self.logText.clear()
        
        # Broadcast log cleared event
        if self.websocket_server and self.websocket_server.is_running:
            self.websocket_server.broadcast_event("logs", "logs_cleared", {
                "timestamp": time.time(),
                "log_file": os.path.basename(self.current_log) if self.current_log else None
            })
    def copyToClipboard(self):
        """Copy log content to clipboard"""
        self.logText.selectAll()
        self.logText.copy()
        self.logText.moveCursor(QTextCursor.Start)
        
        QMessageBox.information(
            self,
            "Copied to Clipboard",
            "Log content has been copied to clipboard."
        )
    
    def browseLogFile(self):
        """Browse for a log file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Log File",
            "",
            "Log Files (*.log);;All Files (*.*)"
        )
        
        if file_path:
            # Add to log files list if not already there
            if file_path not in self.log_files:
                self.log_files.append(file_path)
                self.log_selector.addItem(os.path.basename(file_path), file_path)
            
            # Select the file
            index = self.log_selector.findData(file_path)
            if index >= 0:
                self.log_selector.setCurrentIndex(index)
    
    def checkLogUpdates(self):
        """Periodic check for log updates"""
        # This is handled by the LogWatcher class
        pass
    
    def onLogUpdated(self, filename, new_content):
        """Handle new log content"""
        if filename == self.current_log:
            self.applyContentFilter(new_content)
            
            # Update status
            file_size = os.path.getsize(filename)
            modified_time = datetime.fromtimestamp(os.path.getmtime(filename))
            self.statusLabel.setText(
                f"Log: {os.path.basename(filename)} | Size: {file_size / 1024:.1f} KB | "
                f"Last modified: {modified_time.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            # Buffer this update for WebSocket broadcasting
            self.bufferLogUpdate(filename, new_content)
    
    def getFilterData(self):
        """Get filter data for WebSocket broadcasts"""
        return {
            "filter_text": self.filter_text,
            "log_level": self.log_level,
            "auto_scroll": self.auto_scroll,
            "current_log": os.path.basename(self.current_log) if self.current_log else None
        }
    
    def getLogFileData(self, filename=None):
        """Get log file data for WebSocket broadcasts"""
        if not filename and self.current_log:
            filename = self.current_log
            
        if not filename or not os.path.exists(filename):
            return {
                "log_file": None,
                "content": "",
                "exists": False
            }
            
        try:
            # Only read the last N lines to avoid sending huge logs
            max_lines = 500
            with open(filename, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
                if len(lines) > max_lines:
                    content = ''.join(lines[-max_lines:])
                    truncated = True
                else:
                    content = ''.join(lines)
                    truncated = False
                
            file_size = os.path.getsize(filename)
            modified_time = datetime.fromtimestamp(os.path.getmtime(filename))
            
            return {
                "log_file": os.path.basename(filename),
                "full_path": filename,
                "content": content,
                "size": file_size,
                "size_kb": f"{file_size / 1024:.1f}",
                "modified": modified_time.strftime('%Y-%m-%d %H:%M:%S'),
                "exists": True,
                "truncated": truncated
            }
        except Exception as e:
            logger.error(f"Error getting log file data: {e}")
            return {
                "log_file": os.path.basename(filename),
                "error": str(e),
                "exists": False
            }
    
    def getAvailableLogsData(self):
        """Get data about available log files"""
        logs_data = []
        for log_file in self.log_files:
            if os.path.exists(log_file):
                logs_data.append({
                    "name": os.path.basename(log_file),
                    "path": log_file,
                    "size_kb": f"{os.path.getsize(log_file) / 1024:.1f}",
                    "modified": datetime.fromtimestamp(os.path.getmtime(log_file)).strftime('%Y-%m-%d %H:%M:%S')
                })
        
        return {
            "logs": logs_data,
            "current_log": os.path.basename(self.current_log) if self.current_log else None
        }
    
    def bufferLogUpdate(self, filename, content):
        """Buffer log updates for batch broadcasting"""
        # Only buffer if we have a WebSocket server
        if not self.websocket_server or not self.websocket_server.is_running:
            return
            
        # Add to buffer
        self.log_buffer.append({
            "log_file": os.path.basename(filename),
            "content": content,
            "timestamp": time.time()
        })
    
    def sendBufferedLogUpdates(self):
        """Send buffered log updates to WebSocket clients"""
        if not self.websocket_server or not self.websocket_server.is_running or not self.log_buffer:
            return
            
        # Combine all buffered updates
        combined_content = ""
        log_file = None
        
        for update in self.log_buffer:
            combined_content += update["content"]
            log_file = update["log_file"]
        
        # Clear buffer
        self.log_buffer = []
        
        # Broadcast combined update
        self.logUpdated.emit({
            "log_file": log_file,
            "content": combined_content,
            "timestamp": time.time()
        })
    
    def broadcastLogUpdate(self, log_data):
        """Broadcast log update to all WebSocket clients"""
        if hasattr(self, 'websocket_server') and self.websocket_server and self.websocket_server.is_running:
            self.websocket_server.broadcast_event("logs", "log_update", log_data)
    
    def broadcastFilterUpdate(self, filter_data):
        """Broadcast filter update to all WebSocket clients"""
        if hasattr(self, 'websocket_server') and self.websocket_server and self.websocket_server.is_running:
            self.websocket_server.broadcast_event("logs", "filter_update", filter_data)
    
    def broadcastAvailableLogs(self):
        """Broadcast available logs to all WebSocket clients"""
        if hasattr(self, 'websocket_server') and self.websocket_server and self.websocket_server.is_running:
            self.websocket_server.broadcast_event("logs", "available_logs", self.getAvailableLogsData())

    def closeEvent(self, event):
        """Handle panel close event"""
        # Stop the log watcher thread
        if hasattr(self, 'log_watcher'):
            self.log_watcher.stop()
            self.log_watcher.wait()
        
        event.accept()

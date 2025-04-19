import asyncio
import json
import logging
import secrets
import uuid
import threading
import time
from typing import Dict, List, Any, Optional, Callable, Set
import websockets
from websockets.server import WebSocketServerProtocol
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer

# Import LastOasisManager functions
import LastOasisManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='websocket.log',
    filemode='a'
)
logger = logging.getLogger('WebSocketServer')

class WebSocketMessage:
    """Message structure for WebSocket communication"""
    def __init__(self, event_type: str, action: str, data: Dict[str, Any] = None, auth: str = None):
        self.event_type = event_type  # command, status, notification
        self.action = action  # specific action name
        self.data = data or {}  # payload data
        self.auth = auth  # authentication token
    
    @classmethod
    def from_json(cls, json_str: str) -> 'WebSocketMessage':
        """Create a message from JSON string"""
        try:
            data = json.loads(json_str)
            return cls(
                event_type=data.get('event_type', ''),
                action=data.get('action', ''),
                data=data.get('data', {}),
                auth=data.get('auth', '')
            )
        except json.JSONDecodeError:
            logger.error(f"Failed to parse message: {json_str}")
            return cls("error", "invalid_json")
    
    def to_json(self) -> str:
        """Convert message to JSON string"""
        return json.dumps({
            'event_type': self.event_type,
            'action': self.action,
            'data': self.data,
            'timestamp': time.time()
        })

class WebSocketServer(QObject):
    """WebSocket server that interfaces with LastOasisManager and GUI"""
    
    # PyQt signals for GUI communication
    client_connected = pyqtSignal(str)
    client_disconnected = pyqtSignal(str)
    message_received = pyqtSignal(str, str)  # client_id, message
    server_status_changed = pyqtSignal(bool)  # is_running
    
    def __init__(self, host='localhost', port=8765, auth_key=None):
        super().__init__()
        self.host = host
        self.port = port
        self.auth_key = auth_key or secrets.token_hex(16)
        self.clients: Dict[str, WebSocketServerProtocol] = {}
        self.server = None
        self.server_task = None
        self.loop = None
        self.is_running = False
        self.command_handlers = {
            'start_server': self._handle_start_server,
            'stop_server': self._handle_stop_server,
            'restart_server': self._handle_restart_server,
            'get_status': self._handle_get_status,
            'check_updates': self._handle_check_updates,
            'get_config': self._handle_get_config,
            'update_config': self._handle_update_config,
            'get_logs': self._handle_get_logs,
            'send_admin_message': self._handle_send_admin_message,
        }
        
        # Keep track of event listeners
        self._event_listeners: Dict[str, Set[Callable]] = {}
        
        # Set up timer for periodic status updates
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.send_status_update)
        self.status_timer.setInterval(5000)  # 5 seconds
    
    def start(self):
        """Start the WebSocket server in a separate thread"""
        if not self.is_running:
            self.server_thread = threading.Thread(target=self._run_server_thread, daemon=True)
            self.server_thread.start()
            self.status_timer.start()
            logger.info(f"WebSocket server starting on {self.host}:{self.port}")
            return True
        return False
    
    def stop(self):
        """Stop the WebSocket server"""
        if self.is_running and self.loop:
            asyncio.run_coroutine_threadsafe(self._stop_server(), self.loop)
            self.server_thread.join(timeout=5)
            self.status_timer.stop()
            self.is_running = False
            self.server_status_changed.emit(False)
            logger.info("WebSocket server stopped")
            return True
        return False
    
    def _run_server_thread(self):
        """Run the server in a separate thread with its own event loop"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        try:
            self.loop.run_until_complete(self._run_server())
            self.loop.run_forever()
        except Exception as e:
            logger.error(f"WebSocket server error: {e}")
        finally:
            self.loop.close()
            self.is_running = False
            self.server_status_changed.emit(False)
    
    async def _run_server(self):
        """Start the WebSocket server"""
        self.server = await websockets.serve(
            self._handle_client,
            self.host,
            self.port
        )
        self.is_running = True
        self.server_status_changed.emit(True)
        logger.info(f"WebSocket server running on {self.host}:{self.port}")
    
    async def _stop_server(self):
        """Stop the WebSocket server"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            
        if self.loop:
            for task in asyncio.all_tasks(self.loop):
                if task is not asyncio.current_task():
                    task.cancel()
            
            self.loop.stop()
    
    async def _handle_client(self, websocket: WebSocketServerProtocol, path: str):
        """Handle client connection and messages"""
        client_id = str(uuid.uuid4())
        authenticated = False
        
        try:
            # Add client to clients dict
            self.clients[client_id] = websocket
            self.client_connected.emit(client_id)
            logger.info(f"Client connected: {client_id}")
            
            # Handle messages
            async for message_text in websocket:
                try:
                    message = WebSocketMessage.from_json(message_text)
                    logger.debug(f"Received message: {message.event_type} - {message.action}")
                    
                    # Authentication check
                    if not authenticated:
                        if message.auth == self.auth_key:
                            authenticated = True
                            await self._send_message(websocket, WebSocketMessage(
                                "status", "authenticated", {"status": "success"}
                            ))
                            continue
                        else:
                            await self._send_message(websocket, WebSocketMessage(
                                "error", "authentication_failed", {"status": "error"}
                            ))
                            continue
                    
                    # Process authenticated message
                    if message.event_type == "command":
                        await self._process_command(client_id, websocket, message)
                    elif message.event_type == "subscription":
                        self._process_subscription(client_id, message)
                    
                    # Emit signal for GUI to handle if needed
                    self.message_received.emit(client_id, message_text)
                    
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    await self._send_message(websocket, WebSocketMessage(
                        "error", "processing_error", {"error": str(e)}
                    ))
        
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Connection closed for client {client_id}")
        finally:
            # Clean up client connection
            if client_id in self.clients:
                del self.clients[client_id]
            self.client_disconnected.emit(client_id)
    
    async def _process_command(self, client_id: str, websocket: WebSocketServerProtocol, message: WebSocketMessage):
        """Process a command message from a client"""
        handler = self.command_handlers.get(message.action)
        if handler:
            try:
                response = await handler(message.data)
                await self._send_message(websocket, WebSocketMessage(
                    "response", message.action, response
                ))
            except Exception as e:
                logger.error(f"Error in command handler {message.action}: {e}")
                await self._send_message(websocket, WebSocketMessage(
                    "error", "command_error", {"error": str(e), "command": message.action}
                ))
        else:
            logger.warning(f"Unknown command: {message.action}")
            await self._send_message(websocket, WebSocketMessage(
                "error", "unknown_command", {"command": message.action}
            ))
    
    def _process_subscription(self, client_id: str, message: WebSocketMessage):
        """Process a subscription message from a client"""
        # Add event listeners based on subscription
        event_type = message.data.get("event_type")
        if event_type:
            if event_type not in self._event_listeners:
                self._event_listeners[event_type] = set()
            # Add client to listeners for this event type
            self._event_listeners[event_type].add(client_id)
    
    async def _send_message(self, websocket: WebSocketServerProtocol, message: WebSocketMessage):
        """Send a message to a client"""
        try:
            await websocket.send(message.to_json())
        except Exception as e:
            logger.error(f"Error sending message: {e}")
    
    def broadcast_event(self, event_type: str, action: str, data: Dict[str, Any] = None):
        """Broadcast an event to all connected clients"""
        if not self.clients:
            return
            
        message = WebSocketMessage(event_type, action, data)
        message_json = message.to_json()
        
        for client_id, websocket in self.clients.items():
            asyncio.run_coroutine_threadsafe(
                websocket.send(message_json),
                self.loop
            )
    
    def send_event_to_subscribers(self, event_type: str, action: str, data: Dict[str, Any] = None):
        """Send an event to subscribed clients"""
        if event_type not in self._event_listeners or not self._event_listeners[event_type]:
            return
            
        message = WebSocketMessage("event", action, data)
        message_json = message.to_json()
        
        for client_id in self._event_listeners[event_type]:
            if client_id in self.clients:
                asyncio.run_coroutine_threadsafe(
                    self.clients[client_id].send(message_json),
                    self.loop
                )
    
    @pyqtSlot()
    def send_status_update(self):
        """Send periodic status updates to all clients"""
        if not self.is_running or not self.clients:
            return
            
        # Get current status
        data = {
            "server_running": True,  # This would come from LastOasisManager
            "tile_count": LastOasisManager.config.get("tile_num", 0),
            "mods": LastOasisManager.config.get("mods", "").split(","),
            "timestamp": time.time()
        }
        
        self.broadcast_event("status", "server_status", data)
    
    # Command handlers
    
    async def _handle_start_server(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle start server command"""
        try:
            if "tile_id" in data:
                # Start specific tile
                tile_id = int(data["tile_id"])
                LastOasisManager.start_single_process(tile_id)
                return {"status": "success", "message": f"Started tile {tile_id}"}
            else:
                # Start all tiles
                LastOasisManager.start_processes()
                return {"status": "success", "message": "Started all tiles"}
        except Exception as e:
            logger.error(f"Error starting server: {e}")
            return {"status": "error", "message": str(e)}
    
    async def _handle_stop_server(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle stop server command"""
        try:
            LastOasisManager.stop_processes()
            return {"status": "success", "message": "Stopped all tiles"}
        except Exception as e:
            logger.error(f"Error stopping server: {e}")
            return {"status": "error", "message": str(e)}
    
    async def _handle_restart_server(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle restart server command"""
        try:
            wait_time = int(data.get("wait_time", 1))
            LastOasisManager.restart_all_tiles(wait_time)
            return {"status": "success", "message": f"Restarted all tiles with wait time {wait_time}s"}
        except Exception as e:
            logger.error(f"Error restarting server: {e}")
            return {"status": "error", "message": str(e)}
    
    async def _handle_get_status(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get status command"""
        try:
            # This would need to gather status information from LastOasisManager
            # For now, we'll return some dummy data
            return {
                "status": "success",
                "server_running": True,
                "tile_count": LastOasisManager.config.get("tile_num", 0),
                "mods": LastOasisManager.config.get("mods", "").split(","),
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return {"status": "error", "message": str(e)}
    
    async def _handle_check_updates(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle check updates command"""
        try:
            # Check for both server and mod updates
            server_update = LastOasisManager.check_for_server_update()
            out_of_date, updated_mods_info = LastOasisManager.check_mod_updates()
            
            return {
                "status": "success",
                "server_update_available": server_update,
                "mod_updates_available": len(out_of_date) > 0,
                "outdated_mods": out_of_date
            }
        except Exception as e:
            logger.error(f"Error checking updates: {e}")
            return {"status": "error", "message": str(e)}
    
    async def _handle_get_config(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get config command"""
        try:
            # Return the current configuration
            return {
                "status": "success",
                "config": LastOasisManager.config
            }
        except Exception as e:
            logger.error(f"Error retrieving configuration: {e}")
            return {"status": "error", "message": str(e)}

    async def _handle_update_config(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle update config command"""
        try:
            # Validate that we have configuration data
            if not data or not isinstance(data, dict):
                return {"status": "error", "message": "Invalid configuration data format"}
            
            updated_keys = []
            # Update configuration values
            for key, value in data.items():
                # Skip internal or protected keys that shouldn't be directly modified
                if key.startswith('_') or key in ['auth_key']:
                    continue
                    
                try:
                    # Update the configuration
                    LastOasisManager.config[key] = value
                    updated_keys.append(key)
                except Exception as inner_e:
                    logger.warning(f"Failed to update config key '{key}': {inner_e}")
            
            # Save the updated configuration to file
            LastOasisManager.save_config()
            
            return {
                "status": "success",
                "message": f"Configuration updated successfully",
                "updated_keys": updated_keys,
                "config": LastOasisManager.config
            }
        except Exception as e:
            logger.error(f"Error updating configuration: {e}")
            return {"status": "error", "message": str(e)}

    async def _handle_get_logs(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get logs command"""
        try:
            # Get log file information based on requested filters
            log_file = data.get("log_file", "loman.log")  # Default to main log
            max_lines = int(data.get("max_lines", 500))   # Default to 500 lines
            filter_text = data.get("filter_text", "")     # Optional text filter
            log_level = data.get("log_level", "ALL")      # Optional level filter
            
            # Determine which log file to read
            log_path = log_file
            if not os.path.isabs(log_path):
                # If it's not an absolute path, look in standard locations
                if os.path.exists(log_file):
                    log_path = log_file
                elif os.path.exists(os.path.join("logs", log_file)):
                    log_path = os.path.join("logs", log_file)
                else:
                    # Check in LastOasysManager log folder if configured
                    folder_path = LastOasisManager.config.get('folder_path', '')
                    if folder_path:
                        possible_log_path = os.path.join(folder_path.replace("Binaries\\Win64\\", "Saved\\Logs"), log_file)
                        if os.path.exists(possible_log_path):
                            log_path = possible_log_path
            
            if not os.path.exists(log_path):
                return {
                    "status": "error",
                    "message": f"Log file not found: {log_file}",
                    "log_file": log_file,
                    "exists": False
                }
            
            # Read the log file
            with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
            
            # Apply filters if specified
            if filter_text:
                lines = [line for line in lines if filter_text.lower() in line.lower()]
            
            if log_level != "ALL":
                # Define log levels for filtering
                log_levels = {
                    "DEBUG": 10,
                    "INFO": 20,
                    "WARNING": 30,
                    "ERROR": 40,
                    "CRITICAL": 50
                }
                level_value = log_levels.get(log_level, 0)
                
                # Filter lines by log level
                filtered_lines = []
                for line in lines:
                    for level_name, level_val in log_levels.items():
                        if level_val >= level_value and level_name in line:
                            filtered_lines.append(line)
                            break
                lines = filtered_lines
            
            # Limit number of lines if specified
            if max_lines > 0 and len(lines) > max_lines:
                lines = lines[-max_lines:]
                truncated = True
            else:
                truncated = False
            
            # Get file metadata
            file_size = os.path.getsize(log_path)
            modified_time = os.path.getmtime(log_path)
            
            return {
                "status": "success",
                "log_file": log_file,
                "content": "".join(lines),
                "size": file_size,
                "size_kb": f"{file_size / 1024:.1f}",
                "modified": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(modified_time)),
                "line_count": len(lines),
                "truncated": truncated,
                "exists": True
            }
            
        except Exception as e:
            logger.error(f"Error retrieving logs: {e}")
            return {
                "status": "error",
                "message": str(e),
                "log_file": data.get("log_file", "unknown")
            }

    async def _handle_send_admin_message(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle send admin message command"""
        try:
            message = data.get("message", "").strip()
            if not message:
                return {"status": "error", "message": "Message content is required"}
                
            target_id = data.get("target_id", -1)  # -1 means all tiles
            
            folder_path = LastOasisManager.config.get('folder_path', '')
            if not folder_path:
                return {"status": "error", "message": "Server folder path not configured"}
            
            # Import admin writer to send messages
            import admin_writer
            
            if target_id == -1:
                # Send to all tiles
                tile_num = LastOasisManager.config.get('tile_num', 1)
                for i in range(tile_num):
                    admin_writer.write(message, folder_path, i)
                target_text = "all tiles"
            else:
                # Send to specific tile
                admin_writer.write(message, folder_path, target_id)
                target_text = f"tile {target_id}"
            
            return {
                "status": "success", 
                "message": f"Admin message sent to {target_text}",
                "content": message,
                "target_id": target_id,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"Error sending admin message: {e}")
            return {"status": "error", "message": str(e)}


import os
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, Request, Form, HTTPException, Depends, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import backend functionality
from backend.LastOasisManager import (
    update_config,
    start_processes,
    stop_processes,
    restart_all_tiles,
    check_mod_updates,
    download_mods,
)

# Initialize FastAPI app
app = FastAPI(
    title="Last Oasis Server Manager",
    description="Web interface for managing Last Oasis dedicated servers",
    version="1.0.0"
)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure templates
templates = Jinja2Templates(directory="templates")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Config file path
CONFIG_FILE = "config.json"

# Data models
class ConfigUpdate(BaseModel):
    """Model for configuration updates"""
    key: str
    value: Any

class BackupConfig(BaseModel):
    """Model for backup configuration"""
    backup_path: str
    enable_auto_backup: bool
    backup_redundancy: str
    backup_frequency: str
    backup_days: Optional[List[str]]
    backup_day_of_month: Optional[int]
    backup_time: str
    custom_interval_value: Optional[int]
    custom_interval_unit: Optional[str]
    max_backups: int
    retention_value: int
    retention_unit: str
    auto_backup_retention: int
    manual_backup_retention: int
    update_backup_retention: int
    enable_compression: bool
    compression_method: str
    compression_level: int
    split_backups: bool
    exclude_logs: bool
    enable_verification: bool
    verification_method: str
    verification_frequency: str
    auto_repair: bool
    recreate_failed: bool
    notify_success: bool
    notify_failure: bool
    notification_method: str
    email_recipient: Optional[str]

# Utility functions
def load_config() -> dict:
    """Load configuration from file"""
    try:
        # Import here to avoid circular imports
        import config_utils
        
        # Use the safer config loading utility
        config, success, error = config_utils.load_config_safely(CONFIG_FILE)
        if not success:
            print(f"Error loading config: {error}")
            return {}
        return config
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}

    try:
        with open(CONFIG_FILE, 'w') as file:
            json.dump(config, file, indent=4)
        update_config()  # Update the config in the backend
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False

def format_datetime(dt=None):
    """Format datetime for display"""
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%Y-%m-%d %H:%M:%S")

# Helper functions for context data
def get_context_data():
    """Get common context data for templates"""
    return {
        "current_time": format_datetime(),
        "app_version": "1.0.0",
    }

# Route handlers
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main dashboard page"""
    context = {
        "request": request,
        **get_context_data()
    }
    return templates.TemplateResponse("index.html", context)

@app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    """Serve the configuration page"""
    config = load_config()
    context = {
        "request": request,
        "config": config,
        **get_context_data()
    }
    return templates.TemplateResponse("config.html", context)

@app.get("/servers", response_class=HTMLResponse)
async def servers_page(request: Request):
    """Serve the servers management page"""
    context = {
        "request": request,
        "config": load_config(),
        **get_context_data()
    }
    return templates.TemplateResponse("servers.html", context)

@app.get("/mods", response_class=HTMLResponse)
async def mods_page(request: Request):
    """Serve the mods management page"""
    context = {
        "request": request,
        "config": load_config(),
        **get_context_data()
    }
    return templates.TemplateResponse("mods.html", context)

@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    """Serve the logs page"""
    context = {
        "request": request,
        "config": load_config(),
        **get_context_data()
    }
    return templates.TemplateResponse("logs.html", context)

# API Endpoints
@app.get("/api/dashboard")
async def get_dashboard():
    """Get the dashboard data including server status, mod status, and system status"""
    try:
        # Sample data - in a real application, this would be retrieved from your backend
        servers = [
            {
                "server_id": "LO_Server0",
                "tile_name": "Nomad Valley",
                "status": "online",
                "players": "12/40",
                "uptime": "12h 30m"
            },
            {
                "server_id": "LO_Server1",
                "tile_name": "Cradle Valley",
                "status": "online",
                "players": "8/40",
                "uptime": "6h 15m"
            }
        ]
        
        mods = [
            {
                "name": "Improved Walkers",
                "version": "1.5.2",
                "last_update": "2025-04-15",
                "status": "Up to date"
            },
            {
                "name": "Resource Plus",
                "version": "2.1.0",
                "last_update": "2025-04-10",
                "status": "Update available"
            }
        ]
        
        system = {
            "server_update_available": False,
            "mod_updates_available": True,
            "last_check_time": format_datetime()
        }
        
        return {
            "servers": servers,
            "mods": mods,
            "system": system
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard data: {str(e)}")

@app.get("/api/servers")
async def get_servers():
    """Get list of servers and their status"""
    try:
        # In a real application, this would connect to the LastOasisManager backend
        # For now, return sample data
        servers = [
            {
                "server_id": "LO_Server0",
                "tile_name": "Nomad Valley",
                "status": "online",
                "players": "12/40",
                "uptime": "12h 30m",
                "ip": "127.0.0.1",
                "port": "7777",
                "query_port": "27015"
            },
            {
                "server_id": "LO_Server1",
                "tile_name": "Cradle Valley",
                "status": "online", 
                "players": "8/40",
                "uptime": "6h 15m",
                "ip": "127.0.0.1",
                "port": "7778",
                "query_port": "27016"
            },
            {
                "server_id": "LO_Server2",
                "tile_name": "Oasis Canyon",
                "status": "offline",
                "players": "0/40",
                "uptime": "0m",
                "ip": "127.0.0.1", 
                "port": "7779",
                "query_port": "27017"
            }
        ]
        
        return servers
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get server list: {str(e)}")

@app.get("/api/mods")
async def get_mods():
    """Get list of mods and their status"""
    try:
        # In a real application, this would read from the mod_checker module
        # For now, return sample data
        mods = [
            {
                "name": "Improved Walkers",
                "workshop_id": "2578752449",
                "version": "1.5.2",
                "last_update": "2025-04-15",
                "status": "Up to date",
                "icon_url": "/static/img/mod-placeholder.png"
            },
            {
                "name": "Resource Plus",
                "workshop_id": "2673391719",
                "version": "2.1.0",
                "last_update": "2025-04-10",
                "status": "Update available",
                "icon_url": "/static/img/mod-placeholder.png"
            },
            {
                "name": "Better Building",
                "workshop_id": "2845692103",
                "version": "3.2.1",
                "last_update": "2025-04-01",
                "status": "Up to date",
                "icon_url": "/static/img/mod-placeholder.png"
            }
        ]
        
        return mods
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get mod list: {str(e)}")

@app.post("/api/servers/action")
async def server_action(action_data: dict):
    """Perform an action on a server (start, stop, restart)"""
    try:
        server_id = action_data.get("server_id")
        action = action_data.get("action")
        
        if not server_id or not action:
            raise HTTPException(status_code=400, detail="server_id and action must be provided")
        
        # Validate action
        if action not in ["start", "stop", "restart"]:
            raise HTTPException(status_code=400, detail=f"Invalid action: {action}")
        
        # In a real application, this would call the LastOasisManager functions
        # For now, just return success
        actions_map = {
            "start": lambda id: print(f"Starting server {id}..."),
            "stop": lambda id: print(f"Stopping server {id}..."),
            "restart": lambda id: print(f"Restarting server {id}...")
        }
        
        # Execute the action
        actions_map[action](server_id)
        
        return {
            "status": "success",
            "message": f"{action.capitalize()} command sent to server {server_id}"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to perform action: {str(e)}")

@app.post("/api/servers/start")
async def start_servers():
    """Start all server processes"""
    try:
        # Call the backend function
        start_processes()
        print("Starting all servers...")
        
        return {
            "status": "success",
            "message": "Servers started successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start servers: {str(e)}")

@app.post("/api/servers/stop")
async def stop_servers():
    """Stop all server processes"""
    try:
        # Call the backend function
        stop_processes()
        print("Stopping all servers...")
        
        return {
            "status": "success",
            "message": "Servers stopped successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop servers: {str(e)}")

@app.post("/api/servers/restart")
async def restart_servers(delay: int = 60):
    """Restart all server processes with optional delay"""
    try:
        # Call the backend function
        restart_all_tiles(delay)
        print(f"Restarting all servers with {delay}s delay...")
        
        return {
            "status": "success",
            "message": f"Servers restarting with {delay}s delay"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to restart servers: {str(e)}")
@app.post("/api/admin/message")
async def send_admin_message(message_data: dict):
    """Send an admin message to all or specific servers"""
    try:
        message = message_data.get("message")
        server_ids = message_data.get("server_ids", [])
        
        if not message:
            raise HTTPException(status_code=400, detail="message must be provided")
        
        # In a real application, use admin_writer to write messages
        # For demo, just print what would happen
        if server_ids:
            print(f"Sending message to servers {server_ids}: {message}")
        else:
            print(f"Broadcasting to all servers: {message}")
            
        return {
            "status": "success",
            "message": "Admin message sent successfully",
            "sent_to": server_ids or "all servers"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send admin message: {str(e)}")

@app.get("/api/mods/check")
async def check_for_mod_updates():
    """Check for mod updates"""
    try:
        # Call the backend function
        out_of_date, updated_mods_info = check_mod_updates()
        
        return {
            "status": "success", 
            "updates_available": len(out_of_date) > 0,
            "outdated_mods": out_of_date
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check for mod updates: {str(e)}")

@app.post("/api/mods/update")
async def update_mods():
    """Update all out-of-date mods"""
    try:
        # Check for updates and then download them
        out_of_date, updated_mods_info = check_mod_updates()
        
        if out_of_date:
            download_mods(out_of_date, updated_mods_info)
            return {
                "status": "success",
                "message": f"Updated {len(out_of_date)} mods"
            }
        else:
            return {
                "status": "success",
                "message": "All mods are up to date"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update mods: {str(e)}")

@app.get("/api/config")
async def get_config():
    """Get the current configuration"""
    config = load_config()
    return JSONResponse(content=config)

@app.post("/api/config")
async def update_config_endpoint(config_data: dict):
    """Update the configuration"""
    current_config = load_config()
    # Update with new values
    current_config.update(config_data)
    # Save updated config
    if save_config(current_config):
        return {"status": "success", "message": "Configuration updated successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to save configuration")

@app.post("/api/config/backup")
async def backup_config():
    """Create a backup of the current configuration"""
    try:
        config = load_config()
        backup_filename = f"config_backup_{int(time.time())}.json"
        with open(backup_filename, 'w') as file:
            json.dump(config, file, indent=4)
        return {"status": "success", "message": f"Configuration backed up to {backup_filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to backup configuration: {str(e)}")

@app.post("/api/config/restore")
async def restore_config(file: UploadFile = File(...)):
    """Restore configuration from a backup file"""
    try:
        content = await file.read()
        config = json.loads(content.decode())
        # Validate the configuration has required fields
        required_fields = ["folder_path", "steam_cmd_path", "identifier", "slots"]
        missing_fields = [field for field in required_fields if field not in config]
        
        if missing_fields:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid configuration file: Missing required fields: {', '.join(missing_fields)}"
            )
            
        # Save the validated configuration
        if not save_config(config):
            raise HTTPException(
                status_code=500, 
                detail="Failed to write configuration to disk"
            )
            
        return {"status": "success", "message": "Configuration restored successfully"}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")
    except HTTPException:
        raise
    except IOError as e:
        raise HTTPException(status_code=500, detail=f"File operation failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to restore configuration: {str(e)}")

# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)


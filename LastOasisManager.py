import json
import signal
import subprocess
import sys
import time
import threading
import os
import shutil
import ctypes
import psutil
import re
import logging

# Windows process creation flags
CREATE_NEW_CONSOLE = 0x00000010
DETACHED_PROCESS = 0x00000008
CREATE_NO_WINDOW = 0x08000000
STARTF_USESHOWWINDOW = 0x00000001
SW_SHOW = 5

# Third-party imports
import requests

# Local imports
import admin_writer
from mod_checker import add_new_mod_ids, read_json, update_mods_info
from TileTracker import get_tracker

# Expose important functions at module level
__all__ = ['start_processes', 'stop_processes', 'restart_all_tiles', 'update_config', 'get_tracker']

# Set up logging
# Create console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(message)s')  # Simpler format for console
console_handler.setFormatter(console_formatter)

# Create file handler with encoding specification
file_handler = logging.FileHandler('loman.log', mode='a', encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)

# Set up root logger
logger = logging.getLogger('LOManager')
logger.setLevel(logging.INFO)
# Prevent duplicate messages by setting propagate to False
logger.propagate = False
# Clear any existing handlers
logger.handlers.clear()
logger.addHandler(file_handler)
logger.addHandler(console_handler)

stop_events = []
processes = []
wait_restart_time = 0
config = {}
config_path = "config.json"  # Add this line
crash_total = 0
last_server_check_time = 0  # Track when we last checked for server updates

# Initialize tile tracker
tile_tracker = None

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)


def send_discord_message(webhook_url, message, server_id=None):
    """
    Send a message to Discord via webhook
    If server_id is provided, attempt to include the tile name
    """
    if server_id:
        tile_name = tile_tracker.get_tile_name(server_id, server_id)
        message = message.replace("Tile", f"{tile_name}")
    
    # Log once, both to file and console
    logger.info(f"Discord Message: {message}")
    data = {"content": message}
    response = requests.post(webhook_url, json=data)

    return response.status_code

def check_for_log_updates():
    """Check log files for tile name updates if tracker is initialized"""
    if tile_tracker:
        # Only scan logs if tracker is properly initialized
        try:
            tile_tracker.scan_logs_for_tile_names()
        except Exception as e:
            logger.error(f"Error scanning logs for tile names: {e}")


def run_process(command_args, stop_event):
    """Run a server process and handle crashes and restarts"""
    server_id = None
    for arg in command_args:
        if arg.startswith("-identifier="):
            server_id = arg.split("=")[1]
            break
    
    while not stop_event.is_set():
        # Only log once via logger
        logger.info(f"Starting server with command: {' '.join(command_args)}")
        
        # Check for tile name updates before starting
        check_for_log_updates()
        
        process = None
        try:
            # Get executable path and working directory
            exe_path = command_args[0]
            working_dir = os.path.dirname(exe_path)
            
            # Create process with proper Windows creation flags
            process = subprocess.Popen(
                command_args,
                creationflags=CREATE_NEW_CONSOLE,
                cwd=working_dir
            )
            
            # Send Discord message directly without duplicate logging
            if server_id:
                tile_name = tile_tracker.get_tile_name(server_id, server_id)
                if tile_name:
                    data = {"content": f"{tile_name} is starting up"}
                    requests.post(config["server_status_webhook"], json=data)

            # Monitor process
            while process.poll() is None and not stop_event.is_set():
                time.sleep(1)

            # Handle process exit
            if stop_event.is_set():
                # Send Discord message directly without duplicate logging
                if server_id:
                    tile_name = tile_tracker.get_tile_name(server_id, server_id) or f"Tile {server_id}"
                    data = {"content": f"{tile_name} is being restarted for mod update"}
                    requests.post(config["server_status_webhook"], json=data)
                logger.info(f"Stopping server {server_id if server_id else 'unknown'}")
                try:
                    if process:
                        kill_process = psutil.Process(process.pid)
                        for proc in kill_process.children(recursive=True):
                            proc.kill()
                        kill_process.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                    logger.debug(f"Process already terminated: {e}")
                break
            else:
                # Send Discord message directly without duplicate logging
                if server_id:
                    tile_name = tile_tracker.get_tile_name(server_id, server_id) or f"Tile {server_id}"
                    data = {"content": f"{tile_name} Crashed: Restarting"}
                    requests.post(config["server_status_webhook"], json=data)
                logger.info(f"Server {server_id if server_id else 'unknown'} has exited. It will be checked for restart conditions.")
                global crash_total
                crash_total += 1
                time.sleep(1)
        except Exception as e:
            logger.error(f"Failed to start process: {e}")
            time.sleep(1)  # Wait before retry
        finally:
            # Ensure process cleanup
            if process:
                try:
                    # Only try to terminate if process hasn't already exited
                    if process.poll() is None:
                        process.terminate()
                except Exception as e:
                    logger.debug(f"Error cleaning up process: {e}")


def start_processes():
    """Start all server processes based on tile_num configuration"""
    if "tile_num" not in config:
        logger.error("No tile_num specified in configuration")
        return False

    logger.info("Starting all server processes")
    success = True
    for i in range(config["tile_num"]):
        if not start_single_process(i):
            logger.error(f"Failed to start server tile {i}")
            success = False
            
    return success



def start_single_process(tile_id):
    """Start a single server process"""
    logger.info(f"Attempting to start server tile {tile_id}")
    
    # Validate that we have needed configuration
    critical_fields = ["folder_path", "backend", "customer_key", "provider_key", "connection_ip", 
                      "slots", "identifier", "start_port", "start_query_port"]
    
    # Only log configuration at debug level
    logger.debug(f"Configuration for tile {tile_id}:")
    missing_fields = []
    for field in critical_fields:
        value = config.get(field, "NOT SET")
        if field not in config or not config.get(field):
            missing_fields.append(field)
        logger.debug(f"  - {field}: {value}")
    
    if missing_fields:
        error_msg = f"Cannot start server tile {tile_id}. Missing critical configuration: {', '.join(missing_fields)}"
        logger.error(error_msg)
        return False
    
    # Verify executable path exists
    exe_path = os.path.join(config["folder_path"], "MistServer-Win64-Shipping.exe")
    if not os.path.exists(exe_path):
        logger.error(f"Server executable not found at {exe_path}")
        return False
    
    logger.debug(f"Using executable: {exe_path}")  # Move to debug level
        
    global processes, stop_events
    
    # Ensure arrays are large enough
    while len(processes) <= tile_id:
        processes.append(None)
    while len(stop_events) <= tile_id:
        stop_events.append(None)
    
    # If there's already a process at this index, stop it
    if processes[tile_id] is not None:
        logger.info(f"Existing process found for tile {tile_id}, stopping it first")
        if stop_events[tile_id] is not None:
            stop_events[tile_id].set()
        processes[tile_id].join()
    
    try:
        # Get absolute path to executable and normalize it
        exe_path = os.path.abspath(os.path.join(config["folder_path"], "MistServer-Win64-Shipping.exe"))
        exe_path = os.path.normpath(exe_path)
        
        # Build command args list with normalized executable path
        command_args = [
            exe_path,  # Use normalized path
            f"-identifier=Disc0oasis{tile_id}",
            f"-port={config['start_port'] + tile_id}",
            f"-QueryPort={config['start_query_port'] + tile_id}",
            "-log",
            "-messaging",
            "-noupnp",
            "-NoLiveServer",
            "-EnableCheats",
            f"-backendapiurloverride={config['backend']}",
            f"-CustomerKey={config['customer_key']}",
            f"-ProviderKey={config['provider_key']}",
            f"-slots={config['slots']}",
            f"-OverrideConnectionAddress={config['connection_ip']}"
        ]
        
        # Add mods if configured
        if "mods" in config and config["mods"]:
            command_args.append(f"-mods={config['mods']}")
        
        # Log the command for debugging
        # Log the command for debugging
        logger.debug(f"Command arguments: {command_args}")
        # Detailed logging of command already done in run_process()
        # Check if ports are in use - do this as a warning only, not a fatal error
        port = config["start_port"] + tile_id
        query_port = config["start_query_port"] + tile_id
        
        port_warnings = []
        try:
            # Check if ports are already in use
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            result = s.connect_ex(('127.0.0.1', port))
            if result == 0:
                warning_msg = f"Port {port} is already in use - this may cause conflicts"
                port_warnings.append(warning_msg)
                logger.warning(warning_msg)
            s.close()
            
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            result = s.connect_ex(('127.0.0.1', query_port))
            if result == 0:
                warning_msg = f"Query port {query_port} is already in use - this may cause conflicts"
                port_warnings.append(warning_msg)
                logger.warning(warning_msg)
            s.close()
        except Exception as e:
            logger.warning(f"Could not check port availability: {e}")
        
        # Start the process regardless of port warnings
        stop_event = threading.Event()
        stop_events[tile_id] = stop_event
        process = threading.Thread(target=run_process, args=(command_args, stop_event))
        process.start()
        processes[tile_id] = process
        
        # Log success with any warnings
        if port_warnings:
            logger.info(f"Process thread started for tile {tile_id} with warnings: {port_warnings}")
            logger.warning(f"Started tile {tile_id} with potential port conflicts")
        else:
            logger.info(f"Process thread started for tile {tile_id}")
            
        return True
    except Exception as e:
        error_msg = f"Failed to start server tile {tile_id}: {str(e)}"
        logger.error(error_msg)  # Will handle both file and console output
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False


def stop_processes():
    """ Stop all processes gracefully """
    logger.info("Stopping all server processes...")
    
    # Set all stop events
    for event in stop_events:
        if event is not None:
            event.set()

    # Wait for all processes to finish
    for process in processes:
        if process is not None:
            process.join()
    
    logger.info("All server processes stopped")


def update_config():
    global config
    try:
        # Remove redundant logging
        logger.debug(f"Loading configuration from: {config_path}")  # Change to debug level
        
        # Import config_utils here to avoid circular imports
        import config_utils
        
        loaded_config, success, error = config_utils.load_config_safely(config_path, apply_defaults=True)
        if not success:
            logger.error(f"Error loading configuration: {error}")
            return False
            
        # Validate configuration
        is_valid, missing_fields, updated_config = config_utils.validate_config(loaded_config, apply_defaults=True)
        config.update(updated_config)
        
        if not is_valid:
            logger.warning(f"Missing required configuration fields: {', '.join(missing_fields)}")
            # Continue with defaults where possible
        
        # Log configuration summary once at info level
        logger.info("Configuration loaded successfully:")
        logger.info(f"  - tile_num: {config.get('tile_num', 'NOT SET')}")
        logger.info(f"  - identifier: {config.get('identifier', 'NOT SET')}")
        logger.info(f"  - mods: {config.get('mods', '')}")
        logger.info(f"  - folder_path: {config.get('folder_path', 'NOT SET')}")
        
        return True
    except FileNotFoundError:
        logger.error(f"Configuration file not found at {config_path}")
        logger.error(f"Current working directory: {os.getcwd()}")
        return False
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in configuration file: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error loading configuration: {e}")
        return False


def check_mod_updates():
    try:
        if not update_config():
            logger.warning("Failed to update configuration, using existing config values")
        
        mods_info = read_json('mods_info.json')
        logger.debug("Added new mod ids")
        
        out_of_date, updated_mods_info = update_mods_info(mods_info, config["mods"].split(","))
        
        if out_of_date:
            logger.info(f"Out-of-date mods found: {out_of_date}")
        return out_of_date, updated_mods_info
    except requests.RequestException as e:
        logger.error(f"Mod update check failed: {e}")
        return [], None


def download_mods(workshop_ids, updated_mods_info):
    try:
        mods_folder = config["folder_path"] + "Mist/Content/Mods"
        if not os.path.exists(mods_folder):
            # Create the folder if it does not exist
            os.makedirs(mods_folder)

        for item in os.listdir(mods_folder):
            item_path = os.path.join(mods_folder, item)
            try:
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.unlink(item_path)  # Removes files and symbolic links
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)  # Removes directories
            except Exception as e:
                logger.error(f"Failed to delete {item_path}. Reason: {e}")

        for workshop_id in workshop_ids:
            # Split command into executable and arguments
            steamcmd_exe = os.path.join(config["steam_cmd_path"], "steamcmd.exe")
            steamcmd_args = ["+login", "anonymous", "+workshop_download_item", "903950", workshop_id, "+quit"]
            
            # Configure process with proper output handling
            process = subprocess.Popen(
                [steamcmd_exe] + steamcmd_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='cp437',  # Use codepage 437 for steamcmd output
                errors='replace',
                shell=False,  # Changed to False
                creationflags=CREATE_NO_WINDOW,
                bufsize=1  # text=True already provides universal_newlines functionality
            )
            
            # Process workshop download output
            success, _ = handle_steamcmd_output(process, f"Workshop download {workshop_id}")
            if not success:
                continue
            
            #if "Success" in output:  # Check the appropriate keyword based on your steamcmd output
            #    updated = True

        # Copy active mods over
        for workshop_id in config["mods"].split(","):
            src_item = os.path.join(config["steam_cmd_path"] + "steamapps/workshop/content/903950/", workshop_id)
            dest_item = os.path.join(mods_folder, workshop_id)
            try:
                if os.path.isdir(src_item):
                    shutil.copytree(src_item, dest_item)  # Copy directory
                else:
                    shutil.copy2(src_item, dest_item)  # Copy files
                    modinfo_path = os.path.join(dest_item, 'modinfo.json')
                    try:
                        with open(modinfo_path, 'r') as file:
                            mod_data = json.load(file)
                        
                        mod_data["active"] = True
                        
                        with open(modinfo_path, 'w') as file:
                            json.dump(mod_data, file)
                    except FileNotFoundError:
                        logger.warning(f"modinfo.json not found at {modinfo_path}")
                    except json.JSONDecodeError as e:
                        logger.error(f"Error parsing modinfo.json at {modinfo_path}: {e}")
                    except IOError as e:
                        logger.error(f"I/O error when handling modinfo.json at {modinfo_path}: {e}")
            except Exception as e:
                logger.error(f"Failed to copy {src_item} to {dest_item}. Reason: {e}")

        # Write updated data back to the JSON file
        try:
            with open('mods_info.json', 'w') as file:
                json.dump(updated_mods_info, file, indent=4)
        except IOError as e:
            logger.error(f"Failed to write updated mods_info.json: {e}")

    except Exception as e:
        logger.error(f"Error in download_mods: {e}")

    return


def handle_steamcmd_output(process, command_name):
    """
    Helper function to handle steamcmd output consistently
    Returns (success: bool, output_text: str)
    """
    output_lines = []
    stderr_output = None
    try:
        # Read stdout line by line without buffering using iterator
        for line in iter(process.stdout.readline, ''):
            line = line.strip()
            if line:
                # Only log at debug level while collecting
                logger.debug(f"{command_name} output: {line}")
                # Filter out common steamcmd output that tends to get duplicated
                if not any(skip in line.lower() for skip in [
                    "loading steam api...",
                    "connecting anonymously to steam public...",
                    "logged in ok",
                    "waiting for client config...",
                    "downloading item",
                    "success! app '903950'",
                    "success! item"
                ]):
                    output_lines.append(line)
    finally:
        # Ensure proper cleanup
        process.stdout.close()
        stderr_output = process.stderr.read().decode('cp437', errors='replace') if hasattr(process.stderr, 'read') else None
        process.stderr.close()
        returncode = process.wait()
        
        # Handle errors
        if returncode != 0:
            logger.error(f"{command_name} failed with return code {returncode}")
            if stderr_output:
                logger.error(f"{command_name} error: {stderr_output}")
            return False, '\n'.join(output_lines)
        elif stderr_output:
            # Only log stderr at debug level if successful
            logger.debug(f"{command_name} stderr: {stderr_output}")
        
        return True, '\n'.join(output_lines)


def restart_all_tiles(wait):
    global wait_restart_time
    wait_restart_time = 0
    stop_processes()
    time.sleep(5)
    update_game()
    out_of_date, updated_mods_info = check_mod_updates()
    download_mods(out_of_date, updated_mods_info)
    time.sleep(wait)
    start_processes()


def check_for_server_update():
    """
    Check if server files need to be updated by querying Steam for the latest app info.
    Returns True if an update is available, False otherwise.
    """
    try:
        logger.info("Checking for Last Oasis server updates...")
        
        # Split command into executable and arguments
        steamcmd_exe = os.path.join(config["steam_cmd_path"], "steamcmd.exe")
        steamcmd_args = ["+login", "anonymous", "+app_info_update", "1", "+app_info_print", "920720", "+quit"]
        
        try:
            # Log full command at debug level
            logger.debug(f"Running steamcmd with args: {' '.join([steamcmd_exe] + steamcmd_args)}")
                
            # Use Popen with proper creation flags and no shell
            process = subprocess.Popen(
                [steamcmd_exe] + steamcmd_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='cp437',  # Use codepage 437 for steamcmd output
                errors='replace',  # Handle encoding errors gracefully
                shell=False,  # Changed to False
                creationflags=CREATE_NO_WINDOW,
                bufsize=1  # text=True already provides universal_newlines functionality
            )
            success, output = handle_steamcmd_output(process, "Steam update check")
            if not success:
                return False
                
            # Look for updates needed
            if any(phrase in output for phrase in ["Update Required", "Update required"]):
                logger.info("Server update available - update required by Steam")
                return True
            logger.info("No server updates detected")
            return False
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Steam command failed: {e}")
            if e.output:
                logger.error(f"Error output: {e.output}")
            return False
            
    except Exception as e:
        logger.error(f"Error checking for server updates: {e}")
        return False


def update_game():
    # Define the SteamCMD command
    try:
        logger.info("Starting Last Oasis server update via Steam")
        
        # Split command into executable and arguments
        steamcmd_exe = os.path.join(config["steam_cmd_path"], "steamcmd.exe")
        steamcmd_args = ["+login", "anonymous", "+app_update", "920720", "validate", "+quit"]
        
        # Log full command at debug level
        logger.debug(f"Running steamcmd with args: {' '.join([steamcmd_exe] + steamcmd_args)}")
        
        try:
            # Use Popen with proper creation flags and no shell
            process = subprocess.Popen(
                [steamcmd_exe] + steamcmd_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='cp437',  # Use codepage 437 for steamcmd output
                errors='replace',  # Handle encoding errors gracefully
                shell=False,  # Changed to False
                creationflags=CREATE_NO_WINDOW,
                bufsize=1  # text=True already provides universal_newlines functionality
            )
            
            success, output = handle_steamcmd_output(process, "Steam update")
            if success:
                logger.info("Steam update completed successfully")
            return success
            
        except subprocess.CalledProcessError as e:
            if e.output:
                logger.error(f"Steam update failed with output: {e.output}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to update game: {e}")
        return False


def monitor_tile_names():
    """Background thread to monitor tile names"""
    last_check_time = 0
    check_interval = 30  # 30 seconds between checks
    
    while True:
        try:
            current_time = time.time()
            # Only scan if enough time has passed and tracker is initialized
            if current_time - last_check_time >= check_interval and tile_tracker:
                tile_tracker.scan_logs_for_tile_names()
                last_check_time = current_time
            time.sleep(1)  # Short sleep to prevent CPU spinning
        except Exception as e:
            logger.error(f"Error in tile name monitoring: {e}")
            time.sleep(5)  # Add delay on error to prevent rapid error logging

def main():
    global tile_tracker
    update_config()
    
    # Initialize tile tracker with config
    tile_tracker = get_tracker(
        log_folder=os.path.join(config["folder_path"].replace("Binaries\\Win64\\", ""), "Saved\\Logs"),
        config_path="config.json"
    )
    
    # Start background thread for tile name monitoring
    threading.Thread(target=monitor_tile_names, daemon=True).start()
    
    restart_all_tiles(1)

    # Set default server check interval if not in config
    if "server_check_interval" not in config:
        config["server_check_interval"] = 3600  # Default to once per hour

    while True:
        # Sleep for the shorter of the mod check or server check intervals
        sleep_time = min(config["mod_check_interval"], config["server_check_interval"])
        time.sleep(sleep_time)
        
        # Only log once per check cycle
        logger.debug(f"Running periodic update checks (interval: {sleep_time}s)")
        
        # Check for server updates first
        global last_server_check_time
        current_time = time.time()
        if current_time - last_server_check_time >= config["server_check_interval"]:
            last_server_check_time = current_time
            if check_for_server_update():
                # Handle server update
                logger.info("Server update detected - preparing to restart all tiles")
                restart_msg = f"Last Oasis server update detected! Restarting tiles in {config['restart_time']} seconds."
                send_discord_message(config["server_status_webhook"], restart_msg)
                
                # Single loop for notifications
                for i in range(config["tile_num"]):
                    admin_writer.write(f"Server update available. Restarting in {config['restart_time']} seconds.", 
                                    config["folder_path"], i)
                    
                time.sleep(config["restart_time"])
                restart_all_tiles(1)
                continue  # Skip mod check this cycle

        # Check for mod updates
        out_of_date, updated_mods_info = check_mod_updates()
        if out_of_date:  # Use clear condition
            workshop_links = [f"https://steamcommunity.com/sharedfiles/filedetails/?id={mod}" for mod in out_of_date]
            
            # Single message with all updates
            restart_msg = (f"Out-of-date mods detected. Server restart in {config['restart_time']} seconds.\n"
                         f"Mod updates: {', '.join(workshop_links)}")
            send_discord_message(config["server_status_webhook"], restart_msg)
            
            # Single loop for notifications
            for i in range(config["tile_num"]):
                admin_writer.write(f"Mod update restart in {config['restart_time']} seconds", 
                                 config["folder_path"], i)
            
            time.sleep(config["restart_time"])
            logger.info("Restarting all tiles for mod updates")
            restart_all_tiles(1)


def start_server_management():
    """
    Start the server management process explicitly.
    This function should be called when you want to start the server management,
    rather than having it start automatically on import.
    """
    def signal_handler(signum, frame):
        logger.info("Received shutdown signal, stopping servers gracefully...")
        # Send restart message to each tile once
        for i in range(config["tile_num"]):
            admin_writer.write("Server shutdown in progress", config["folder_path"], i)
        stop_processes()
        logger.info("Server manager stopped")
        cleanup()
        sys.exit(0)

    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        main()
    except KeyboardInterrupt:
        # Let the signal handler handle it
        pass
    except Exception as e:
        logger.error(f"Unexpected error in server management: {e}")
        stop_processes()


def cleanup():
    """Clean up resources before exit"""
    # Close log handlers
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)


# Only run the main function if this script is executed directly (not imported)
if __name__ == "__main__":
    start_server_management()

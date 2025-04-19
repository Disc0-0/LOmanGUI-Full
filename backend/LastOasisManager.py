import json
import signal
import subprocess
import time
import threading
import os
import shutil
import ctypes
import psutil
import re
import logging
from pathlib import Path

# Third-party imports
import requests

# Local imports
from . import admin_writer
from .mod_checker import add_new_mod_ids, read_json, update_mods_info
from .TileTracker import get_tracker

# Expose important functions at module level
__all__ = ['start_processes', 'stop_processes', 'restart_all_tiles', 'update_config', 'get_tracker']

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='loman.log',
    filemode='a'
)
logger = logging.getLogger('LOManager')

stop_events = []
processes = []
wait_restart_time = 0
config = {}
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
    
    logger.info("Discord Message: {}".format(message))
    print("Discord Message: {}".format(message))
    data = {"content": message}
    response = requests.post(webhook_url, json=data)

    return response.status_code

def check_for_log_updates():
    """Periodically check log files for tile name updates"""
    if tile_tracker:
        tile_tracker.scan_logs_for_tile_names()


def extract_server_id(cmd_args):
    """Extract the server ID from the command arguments"""
    if isinstance(cmd_args, list):
        # Handle list of arguments
        for arg in cmd_args:
            if isinstance(arg, str) and arg.startswith("-identifier="):
                return arg[len("-identifier="):]
    else:
            ]

            # Start the process thread
def run_process(cmd_args, stop_event):
    """Run an executable and monitor it."""
    server_id = extract_server_id(cmd_args)
    
    logger.info(f"Starting process with arguments: {cmd_args}")
    print(f"Starting process with arguments: {cmd_args}")
    
    error_log = None
    process = None
    
    while not stop_event.is_set():
        check_for_log_updates()
        
        try:
            # Create error log file
            error_log_path = os.path.join(os.getcwd(), "process_error.log")
            error_log = open(error_log_path, "w")
            
            # Set working directory
            working_dir = config["folder_path"]
            if not os.path.isabs(working_dir):
                working_dir = os.path.abspath(working_dir)
            
            # Create process
            try:
                process = subprocess.Popen(
                    cmd_args,
                    stdout=subprocess.PIPE,
                    stderr=error_log,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                    shell=False,
                    cwd=working_dir
                )
                logger.info(f"Process created successfully with PID: {process.pid}")
            except WindowsError as win_err:
                # Capture specific Windows errors
                logger.error(f"Windows error creating process: {win_err}")
                print(f"Windows error creating process: {win_err}")
                time.sleep(5)
                continue
            except Exception as e:
                logger.error(f"Error creating process: {e}")
                print(f"Error creating process: {e}")
                time.sleep(5)
                continue
            # Log the process info
            logger.info(f"Process started with PID: {process.pid}")
            
            # Check if process started successfully
            if process.poll() is not None:
                error_code = process.returncode
                logger.error(f"Process failed to start. Exit code: {error_code}")
                print(f"Process failed to start. Exit code: {error_code}")
                
                # Try to read error output
                if error_log:
                    error_log.close()
                try:
                    with open(error_log_path, "r") as f:
                        error_content = f.read()
                        if error_content:
                            logger.error(f"Process error output: {error_content}")
                            print(f"Process error output: {error_content}")
                except Exception as e:
                    logger.error(f"Failed to read error log: {e}")
                
                time.sleep(5)
                continue
            
            # Send message that tile is starting
            if server_id:
                time.sleep(10)  # Give the process more time to start and fetch the correct tile name
                tile_name = tile_tracker.get_tile_name(server_id, server_id)
                send_discord_message(config["server_status_webhook"], f"{tile_name} is starting up")

            # Monitor the process
            while process.poll() is None and not stop_event.is_set():
                time.sleep(1)

            logger.info(f"Process stopped or interrupted. Stop event: {stop_event.is_set()}")
            print(f"Process stopped or interrupted. Stop event: {stop_event.is_set()}")

            # Update tile tracker in case logs have new information
            check_for_log_updates()

            # Handle process termination
            if stop_event.is_set():
                send_discord_message(config["server_status_webhook"], "Tile is being restarted for mod update", server_id)
                logger.info("Stopping server process")
                print("Stopping server process")

                try:
                    kill_process = psutil.Process(process.pid)
                    for proc in kill_process.children(recursive=True):
                        proc.kill()
                    kill_process.kill()
                except psutil.NoSuchProcess:
                    logger.warning("Process already terminated")
                except Exception as e:
                    logger.error(f"Error killing process: {e}")
                
                break
            else:
                # Process crashed or exited unexpectedly
                send_discord_message(config["server_status_webhook"], "Tile Crashed: Restarting", server_id)
                logger.info("Server process has exited. It will be checked for restart conditions.")
                print("Server process has exited. It will be checked for restart conditions.")
                
                global crash_total
                crash_total += 1
                
                # Let's check the error log
                try:
                    if error_log:
                        error_log.close()
                    with open("process_error.log", "r") as f:
                        error_content = f.read()
                        if error_content:
                            logger.error(f"Process error output: {error_content}")
                            print(f"Process error output: {error_content}")
                except Exception as e:
                    logger.error(f"Failed to read error log: {e}")
                
                # Wait before restarting
                time.sleep(5)
        
        except Exception as e:
            logger.error(f"Error in process handling: {e}")
            print(f"Error in process handling: {e}")
            
            # Log the full traceback for better debugging
            import traceback
            error_traceback = traceback.format_exc()
            logger.error(f"Detailed error: {error_traceback}")
            
            time.sleep(5)
        finally:
            # Ensure error log is closed
            if error_log and not error_log.closed:
                error_log.close()
            
            # Ensure process resources are freed
            if process and process.poll() is None:
                try:
                    process.kill()
                except Exception:
                    pass

def build_command_args(tile_id):
    """
    Build command arguments as a list for better process handling
    """
    # Build a clean list of arguments without any quoting issues
    exe_path = os.path.normpath(os.path.join(config["folder_path"], "MistServer-Win64-Shipping.exe"))
    
    # Create the command args list with proper parameter handling - using equals format for all parameters
    cmd_args = [
        exe_path,
        "-log",
        "-noeac",
        "-messaging",
        "-NoLiveServer",
        "-noupnp",
        "-EnableCheats",
        "-backendapiurloverride=backend.last-oasis.com",
        f"-CustomerKey={config['customer_key']}",
        f"-ProviderKey={config['provider_key']}",
        f"-slots={config['slots']}",
        f"-OverrideConnectionAddress={config['connection_ip']}",  # Keep this in equals format
        f"-identifier={config['identifier']}{tile_id}",
        f"-port={config['start_port'] + tile_id}",
        f"-QueryPort={config['start_query_port'] + tile_id}"
    ]
    
    # Log both the argument list and the final command line
    logger.info(f"Command arguments list: {cmd_args}")
    # Don't use list2cmdline as it can add unwanted quoting
    cmd_line = " ".join(cmd_args)
    logger.info(f"Command line: {cmd_line}")
    print(f"Command line: {cmd_line}")
    
    return cmd_args

def start_processes():
    """Start all server processes"""
    global processes, stop_events
    processes = []
    stop_events = []
    
    for i in range(config["tile_num"]):
        cmd_args = build_command_args(i)
        stop_event = threading.Event()
        stop_events.append(stop_event)
        process = threading.Thread(target=run_process, args=(cmd_args, stop_event))
        process.start()
        processes.append(process)


def start_single_process(tile_id):
    """Start a single server process"""
    global processes, stop_events
    
    # Ensure arrays are large enough
    while len(processes) <= tile_id:
        processes.append(None)
    while len(stop_events) <= tile_id:
        stop_events.append(None)
    
    # If there's already a process at this index, stop it
    if processes[tile_id] is not None:
        if stop_events[tile_id] is not None:
            stop_events[tile_id].set()
        processes[tile_id].join()
    
    # Build the command arguments as a list
    cmd_args = build_command_args(tile_id)

    stop_event = threading.Event()
    stop_events[tile_id] = stop_event
    process = threading.Thread(target=run_process, args=(cmd_args, stop_event))
    process.start()
    processes[tile_id] = process


def stop_processes():
    """ Stop all processes gracefully """
    for event in stop_events:
        if event is not None:
            event.set()

    for process in processes:
        if process is not None:
            process.join()


def update_config():
    global config
    with open("config.json", 'r') as file:
        config = json.load(file)


def check_mod_updates():
    try:
        update_config()
        mods_info = read_json('mods_info.json')

        print("Added new mod ids")

        out_of_date, updated_mods_info = update_mods_info(mods_info, config["mods"].split(","))

        print("Out-of-date mods:", out_of_date)
        return out_of_date, updated_mods_info
    except requests.RequestException as E:
        print(f"CheckModUpdates failed: {E}")
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
                print(f"Failed to delete {item_path}. Reason: {e}")

        for workshop_id in workshop_ids:
            cmd = f'"{config["steam_cmd_path"]}steamcmd.exe" +login anonymous +workshop_download_item 903950 {workshop_id} +quit'
            process = subprocess.run(cmd, shell=True, text=True, capture_output=True)
            output = process.stdout
            print(output)
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
                    shutil.copy2(src_item, dest_item)
                    modinfo_path = os.path.join(dest_item, 'modinfo.json')
                    try:
                        with open(modinfo_path, 'r') as file:
                            mod_data = json.load(file)
                        
                        mod_data["active"] = True
                        
                        with open(modinfo_path, 'w') as file:
                            json.dump(mod_data, file)
                    except FileNotFoundError:
                        print(f"Warning: modinfo.json not found at {modinfo_path}")
                    except json.JSONDecodeError as e:
                        print(f"Error parsing modinfo.json at {modinfo_path}: {e}")
                    except IOError as e:
                        print(f"I/O error when handling modinfo.json at {modinfo_path}: {e}")
                  # Copy files
            except Exception as e:
                print(f"Failed to copy {src_item} to {dest_item}. Reason: {e}")

        # Write updated data back to the JSON file
        try:
            with open('mods_info.json', 'w') as file:
                json.dump(updated_mods_info, file, indent=4)
        except IOError as e:
            print(f"Failed to write updated mods_info.json: {e}")

    except Exception as E:
        print(E)

    return


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
        print("Checking for Last Oasis server updates...")

        # First, update app info to get the latest version information
        info_cmd = f'{config["steam_cmd_path"]}steamcmd +login anonymous +app_info_update 1 +app_info_print 920720 +quit'
        process = subprocess.run(info_cmd, shell=True, text=True, capture_output=True)
        output = process.stdout

        # We can look for update information in the output
        # For simplicity, we'll compare local and remote build IDs if available
        # or just check if Steam reports a required update
        
        # Look for indications of updates needed
        if "Update Required" in output or "Update required" in output:
            logger.info("Server update available - update required by Steam")
            print("Server update available - update required by Steam")
            return True
            
        # If there's no clear update indicator, we can assume no update is needed
        logger.info("No server updates detected")
        print("No server updates detected")
        return False
            
    except Exception as e:
        logger.error(f"Error checking for server updates: {e}")
        print(f"Error checking for server updates: {e}")
        return False


def update_game():
    # Define the SteamCMD command
    try:
        logger.info("Starting Last Oasis server update via Steam")
        print("Starting Last Oasis server update via Steam")
        steamcmd_command = "{}steamcmd +login anonymous +app_update 920720 validate +quit".format(
            config["steam_cmd_path"])

        print(steamcmd_command)

        process = subprocess.Popen(steamcmd_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Read and print the output line by line
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(output.strip())

        # Capture any remaining output
        stdout, stderr = process.communicate()
        print(stdout)
        if stderr:
            print(stderr)

    except Exception as E:
        print(E)


def monitor_tile_names():
    """Background thread to monitor tile names"""
    while True:
        try:
            check_for_log_updates()
            time.sleep(30)  # Check every 30 seconds
        except Exception as e:
            logger.error(f"Error in tile name monitoring: {e}")

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
        
        # Check for server updates
        global last_server_check_time
        current_time = time.time()
        if current_time - last_server_check_time >= config["server_check_interval"]:
            last_server_check_time = current_time
            server_update_available = check_for_server_update()
            
            if server_update_available:
                logger.info("Server update detected - preparing to restart all tiles")
                send_discord_message(config["server_status_webhook"], 
                                   "Last Oasis server update detected! Restarting tiles in {} seconds.".format(config["restart_time"]))
                
                # Notify players in-game about the restart
                for i in range(config["tile_num"]):
                    admin_writer.write("Server update available. Restarting in {} seconds.".format(config["restart_time"]), 
                                    config["folder_path"], i)
                    
                # Wait before restarting
                time.sleep(config["restart_time"])
                restart_all_tiles(1)
                continue  # Skip mod check after server update

        # Check for mod updates
        out_of_date, updated_mods_info = check_mod_updates()
        if len(out_of_date) != 0:
            workshop = []
            for mod in out_of_date:
                workshop.append("https://steamcommunity.com/sharedfiles/filedetails/?id=" + mod)

            send_discord_message(config["server_status_webhook"], "Out-of-date mods restarting tiles in {} seconds: {}"
                                 .format(config["restart_time"], workshop))
            send_discord_message(config["server_status_webhook"], "Out-of-date mods restarting tiles in {} seconds: {}"
                                 .format(config["restart_time"], workshop))
            # Send restart message to each tile
            for i in range(config["tile_num"]):
                admin_writer.write("Restart", config["folder_path"], i)
            time.sleep(config["restart_time"])
            restart_all_tiles(1)
# Entry point for starting the server management explicitly
def start_server_management():
    """
    Start the server management process explicitly.
    This function should be called when you want to start the server management,
    rather than having it start automatically on import.
    """
    try:
        main()
    except KeyboardInterrupt:
        # Send restart message to each tile
        for i in range(config["tile_num"]):
            admin_writer.write("Restart", config["folder_path"], i)
        # time.sleep(config["restart_time"])
        stop_processes()
        print("Server manager stopped by user")


# Only run the main function if this script is executed directly (not imported)
if __name__ == "__main__":
    start_server_management()

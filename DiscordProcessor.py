import requests
import os
import json
import time

log_folder = r"C:\lastoasis\Mist\Saved\Logs"
WEBHOOK_URL = "https://discord.com/api/webhooks/1247311023715651686/DKtMACagogeL2U-zWpx-TRPH5DyESaGVRhWjQwnZTt8eshR_uXuIGqTExv_m12kMinB"

def send_discord_message(message, color):
    """Send a message to Discord via webhook."""
    data = {
        "embeds": [
            {
                "description": message,
                "color": color
            }
        ]
    }

    try:
        response = requests.post(WEBHOOK_URL, headers={"Content-Type": "application/json"}, data=json.dumps(data))
        response.raise_for_status()  # Raise an error for bad responses
        print("Message sent successfully!")
    except requests.RequestException as e:
        print(f"Failed to send message: {e}")

def process_chat_message(line):
    """Process a chat message and send the appropriate Discord message."""
    if "Chat message from" in line:
        message = ' '.join(line.split()[4:])
        send_discord_message(message, 3447003)  # Blue
    elif "Join succeeded" in line:
        message = ' '.join(line.split()[3:])
        send_discord_message(f"{message} Joined the server", 65280)  # Green
    elif "LogPersistence: tile_name:" in line:
        message = ' '.join(line.split()[2:])
        send_discord_message(f"{message} Tile is ready to join", 65280)  # Green
    elif "killed" in line and "LogGame" in line:
        message = ' '.join(line.split()[1:])
        send_discord_message(message, 16776960)  # Yellow

def monitor_logs(log_files):
    """Monitor log files for new entries."""
    file_objects = {}
    
    for log in log_files:
        try:
            file_path = os.path.join(log_folder, log)
            file_objects[log] = open(file_path, 'r')
            file_objects[log].seek(0, os.SEEK_END)  # Go to the end of the file
        except FileNotFoundError:
            print(f"Log file not found: {log}")
    
    try:
        while True:
            for log, file in file_objects.items():
                line = file.readline()
                if line:
                    print(line.strip())
                    process_chat_message(line.strip())
                else:
                    time.sleep(0.1)  # Small delay to avoid busy waiting
    except KeyboardInterrupt:
        print("Monitoring stopped.")
    finally:
        for file in file_objects.values():
            file.close()  # Close all opened files

if __name__ == "__main__":
    logs_to_monitor = ["Mist.log", "Mist_2.log", "Mist_3.log"]
    monitor_logs(logs_to_monitor)
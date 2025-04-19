import json
import time
import os


import logging

# Configure logger
logger = logging.getLogger("AdminWriter")

def write_to_json(message, folder, server_id=None):
    """Helper function to write a message to a JSON file."""
    try:
        # Get the game's root directory
        game_root = os.path.dirname(os.path.dirname(os.path.dirname(folder)))
        
        if server_id is not None:
            # Write to the server's specific instance directory under WindowsServer
            # Using the server's identifier format: Disc0oasisX
            instance_name = f"Disc0oasis{server_id}"
            server_folder = os.path.join(game_root, "Saved", "Config", "WindowsServer", instance_name)
            admin_file = os.path.join(server_folder, "Game.ini")
            logger.info(f"Writing admin message for server {server_id} to {admin_file}")
        else:
            # Fallback to default location
            server_folder = os.path.join(game_root, "Saved", "Config", "WindowsServer")
            admin_file = os.path.join(server_folder, "Game.ini")
            logger.info(f"Writing admin message to default location: {admin_file}")
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(admin_file), exist_ok=True)
        
        # Write the message in UE4 config format
        config_content = (
            "[/Game/LastOasis/GameMode/BP_GameMode.BP_GameMode_C]\n"
            f'AdminMessage="{message}"\n'
        )
        
        # First write to a temporary file
        temp_file = admin_file + ".tmp"
        with open(temp_file, 'w') as file:
            file.write(config_content)
            
        # Then rename it to the final file to ensure atomic write
        os.replace(temp_file, admin_file)
            
        logger.info(f"Successfully wrote admin message to {admin_file}")
        
    except Exception as e:
        logger.error(f"Error writing admin message: {e}")
        raise


def write(message, folder, server_id=None):
    write_to_json(message, folder, server_id)
    time.sleep(11)
    write_to_json("", folder, server_id)


def main():
    with open("config.json", 'r') as file:
        config = json.load(file)

    user_input = input("Enter your message: ")
    write(user_input, config["folder_path"])
    main()


if __name__ == "__main__":
    main()
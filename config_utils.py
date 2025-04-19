"""
Utility module for handling configuration files in LastOasisManager.
Provides consistent methods for loading, saving, and validating configurations.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List, Tuple

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('ConfigUtils')

# Default configuration file
DEFAULT_CONFIG_PATH = "config.json"

# Required configuration fields
REQUIRED_FIELDS = [
    "folder_path", "steam_cmd_path", "tile_num", "identifier", "slots",
    "backend", "customer_key", "provider_key", "connection_ip", 
    "start_port", "start_query_port", "server_status_webhook"
]

# Default values for configuration fields
DEFAULT_VALUES = {
    "folder_path": "\\lastoasis\\Mist\\Binaries\\Win64",
    "steam_cmd_path": "\\steamcmd\\",
    "tile_num": 3,
    "identifier": "Disc0oasis",
    "slots": 40,
    "backend": "backend.last-oasis.com",
    "customer_key": "YOUR_CUSTOMER_KEY_HERE",
    "provider_key": "YOUR_PROVIDER_KEY_HERE",
    "connection_ip": "127.0.0.1",
    "start_port": 5555,
    "start_query_port": 5556,
    "server_status_webhook": "YOUR_DISCORD_WEBHOOK_URL_HERE",
    "admin_password": "admin",
    "port": 5555,
    "query_port": 5556,
    "region": "EU",
    "mod_update_check_interval": 600,
    "mod_check_interval": 300,
    "restart_time": 300,
    "server_check_interval": 3600,
    "mods": ""
}

def detect_encoding_issues(filepath: str) -> Optional[Dict[str, Any]]:
    """
    Detect encoding issues in a JSON file, such as BOM markers.
    
    Args:
        filepath: Path to the JSON file to check
        
    Returns:
        Dictionary with information about detected issues, or None if file doesn't exist
    """
    if not os.path.exists(filepath):
        logger.error(f"File not found: {filepath}")
        return None
        
    issues = {
        "has_bom": False,
        "encoding": "unknown",
        "file_size": 0,
        "first_bytes": "",
        "can_parse": False,
        "parse_error": None
    }
    
    try:
        # Read file as binary to check for BOM
        with open(filepath, 'rb') as file:
            content = file.read()
            issues["file_size"] = len(content)
            
            # Check for UTF-8 BOM (EF BB BF)
            if content.startswith(b'\xef\xbb\xbf'):
                issues["has_bom"] = True
                issues["encoding"] = "UTF-8 with BOM"
                issues["first_bytes"] = "EF BB BF"
            elif content.startswith(b'\xff\xfe'):
                issues["has_bom"] = True
                issues["encoding"] = "UTF-16 LE with BOM"
                issues["first_bytes"] = "FF FE"
            elif content.startswith(b'\xfe\xff'):
                issues["has_bom"] = True
                issues["encoding"] = "UTF-16 BE with BOM"
                issues["first_bytes"] = "FE FF"
            else:
                issues["has_bom"] = False
                issues["encoding"] = "UTF-8 (no BOM)"
                issues["first_bytes"] = " ".join([f"{b:02X}" for b in content[:10]])
        
        # Try to parse the content
        try:
            # Remove BOM if present
            if issues["has_bom"]:
                if issues["encoding"] == "UTF-8 with BOM":
                    text_content = content[3:].decode('utf-8')
                elif issues["encoding"].startswith("UTF-16"):
                    text_content = content[2:].decode('utf-16')
                else:
                    text_content = content.decode('utf-8')
            else:
                text_content = content.decode('utf-8')
                
            json.loads(text_content)
            issues["can_parse"] = True
        except Exception as e:
            issues["can_parse"] = False
            issues["parse_error"] = str(e)
    
    except Exception as e:
        logger.error(f"Error analyzing file {filepath}: {e}")
        return None
        
    return issues

def load_config_safely(filepath: str = DEFAULT_CONFIG_PATH, apply_defaults: bool = True) -> Tuple[Dict[str, Any], bool, Optional[str]]:
    """
    Safely load a JSON configuration file, handling encoding issues like BOM.
    
    Args:
        filepath: Path to the configuration file
        apply_defaults: Whether to apply default values for missing fields
        
    Returns:
        Tuple containing (config_dict, success, error_message)
        - config_dict: Configuration dictionary (may be empty if loading failed)
        - success: Boolean indicating whether loading succeeded
        - error_message: Error message if loading failed, None otherwise
    """
    if not os.path.exists(filepath):
        error_msg = f"Configuration file not found: {filepath}"
        logger.error(error_msg)
        return {}, False, error_msg
        
    try:
        # First try to detect encoding issues
        issues = detect_encoding_issues(filepath)
        
        if issues and issues["has_bom"]:
            logger.warning(f"BOM detected in {filepath}: {issues['encoding']}")
            
            # Read file as binary and remove BOM
            with open(filepath, 'rb') as file:
                content = file.read()
                
                if issues["encoding"] == "UTF-8 with BOM":
                    text_content = content[3:].decode('utf-8')
                elif issues["encoding"].startswith("UTF-16"):
                    text_content = content[2:].decode('utf-16')
                else:
                    text_content = content.decode('utf-8')
        else:
            # Standard read with utf-8 encoding
            with open(filepath, 'r', encoding='utf-8') as file:
                text_content = file.read()
                
        # Parse JSON
        # Parse JSON
        config = json.loads(text_content)
        
        # Apply default values for missing fields if requested
        if apply_defaults:
            for key, default_value in DEFAULT_VALUES.items():
                if key not in config:
                    logger.warning(f"Missing configuration key '{key}', using default value: {default_value}")
                    config[key] = default_value
        
        logger.info(f"Successfully loaded configuration from {filepath}")
        return config, True, None
    except json.JSONDecodeError as e:
        error_msg = f"JSON parse error in {filepath}: {e}"
        logger.error(error_msg)
        return {}, False, error_msg
    except Exception as e:
        error_msg = f"Error loading configuration from {filepath}: {e}"
        logger.error(error_msg)
        return {}, False, error_msg

def save_config_safely(config: Dict[str, Any], filepath: str = DEFAULT_CONFIG_PATH) -> Tuple[bool, Optional[str]]:
    """
    Safely save a configuration dictionary to a JSON file without BOM.
    
    Args:
        config: Configuration dictionary to save
        filepath: Path where to save the configuration
        
    Returns:
        Tuple containing (success, error_message)
        - success: Boolean indicating whether saving succeeded
        - error_message: Error message if saving failed, None otherwise
    """
    try:
        # Create backup of existing config
        if os.path.exists(filepath):
            backup_path = f"{filepath}.backup"
            try:
                with open(filepath, 'rb') as src, open(backup_path, 'wb') as dst:
                    dst.write(src.read())
                logger.info(f"Created backup of configuration at {backup_path}")
            except Exception as e:
                logger.warning(f"Failed to create backup: {e}")
        
        # Save with UTF-8 encoding, no BOM
        with open(filepath, 'w', encoding='utf-8') as file:
            json.dump(config, file, indent=4)
        
        logger.info(f"Successfully saved configuration to {filepath}")
        return True, None
    except Exception as e:
        error_msg = f"Error saving configuration to {filepath}: {e}"
        logger.error(error_msg)
        return False, error_msg

def validate_config(config: Dict[str, Any], apply_defaults: bool = False) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    Validate that a configuration dictionary has all required fields.
    Optionally apply default values for missing fields.
    
    Args:
        config: Configuration dictionary to validate
        apply_defaults: Whether to apply default values for missing fields
        
    Returns:
        Tuple containing (is_valid, missing_fields, updated_config)
        - is_valid: Boolean indicating whether the configuration is valid
        - missing_fields: List of missing required fields
        - updated_config: Configuration with default values applied (if requested)
    """
    # Create a copy of the config to avoid modifying the original
    updated_config = config.copy()
    
    # Apply defaults for missing fields if requested
    if apply_defaults:
        for field, default_value in DEFAULT_VALUES.items():
            if field not in updated_config:
                updated_config[field] = default_value
                logger.info(f"Applied default value for '{field}': {default_value}")
    
    # Check for missing required fields
    missing_fields = [field for field in REQUIRED_FIELDS if field not in updated_config]
    
    return len(missing_fields) == 0, missing_fields, updated_config

def fix_json_file(filepath: str) -> bool:
    """
    Attempt to fix a JSON file by removing BOM and ensuring proper formatting.
    
    Args:
        filepath: Path to the JSON file to fix
        
    Returns:
        Boolean indicating whether the fix succeeded
    """
    # Check if file exists
    if not os.path.exists(filepath):
        logger.error(f"File not found: {filepath}")
        return False
        
    try:
        # Detect encoding issues
        issues = detect_encoding_issues(filepath)
        
        if not issues:
            logger.error(f"Could not analyze file: {filepath}")
            return False
            
        # If file can already be parsed and has no BOM, nothing to fix
        if issues["can_parse"] and not issues["has_bom"]:
            logger.info(f"No issues detected in {filepath}")
            return True
            
        # Read file content
        with open(filepath, 'rb') as file:
            content = file.read()
            
        # Remove BOM if present
        if issues["has_bom"]:
            if issues["encoding"] == "UTF-8 with BOM":
                content = content[3:]
            elif issues["encoding"].startswith("UTF-16"):
                # Convert from UTF-16 to UTF-8
                if issues["encoding"] == "UTF-16 LE with BOM":
                    text = content[2:].decode('utf-16-le')
                else:
                    text = content[2:].decode('utf-16-be')
                content = text.encode('utf-8')
                
        # Try to parse and pretty-print
        try:
            config = json.loads(content.decode('utf-8'))
            formatted_json = json.dumps(config, indent=4)
            
            # Write back to file
            with open(filepath, 'w', encoding='utf-8') as file:
                file.write(formatted_json)
                
            logger.info(f"Successfully fixed and formatted {filepath}")
            return True
        except json.JSONDecodeError as e:
            logger.error(f"Could not parse JSON even after removing BOM: {e}")
            return False
            
    except Exception as e:
        logger.error(f"Error fixing {filepath}: {e}")
        return False

# Diagnostic function to check and fix all configuration files
def diagnose_and_fix_configs(config_files: List[str] = None) -> Dict[str, Any]:
    """
    Check and fix all configuration files in the application.
    
    Args:
        config_files: List of configuration file paths to check and fix
        
    Returns:
        Dictionary with diagnostic results for each file
    """
    if config_files is None:
        config_files = [
            DEFAULT_CONFIG_PATH,
            os.path.join("backend", "config.json"),
            os.path.join("web_interface", "config.json")
        ]
        
    results = {}
    
    for filepath in config_files:
        if not os.path.exists(filepath):
            results[filepath] = {"exists": False, "message": "File not found"}
            continue
            
        # Check for issues
        issues = detect_encoding_issues(filepath)
        
        if not issues:
            results[filepath] = {"exists": True, "message": "Could not analyze file"}
            continue
            
        # Try to fix if needed
        fixed = False
        if issues["has_bom"] or not issues["can_parse"]:
            fixed = fix_json_file(filepath)
            
        # Store results
        results[filepath] = {
            "exists": True,
            "has_bom": issues["has_bom"],
            "encoding": issues["encoding"],
            "can_parse": issues["can_parse"],
            "fixed": fixed,
            "parse_error": issues["parse_error"]
        }
        
    return results

if __name__ == "__main__":
    # Run diagnostic when script is executed directly
    print("LastOasisManager Configuration Diagnostic Tool")
    print("=============================================")
    
    results = diagnose_and_fix_configs()
    
    for filepath, result in results.items():
        print(f"\nFile: {filepath}")
        if not result["exists"]:
            print("  Status: Not found")
            continue
            
        if "has_bom" in result:
            print(f"  Encoding: {result['encoding']}")
            print(f"  Has BOM: {result['has_bom']}")
            print(f"  Can parse: {result['can_parse']}")
            
            if not result["can_parse"]:
                print(f"  Parse error: {result['parse_error']}")
                
            if result["fixed"]:
                print("  Status: Fixed successfully")
            else:
                if result["has_bom"] or not result["can_parse"]:
                    print("  Status: Could not fix issues")
                else:
                    print("  Status: No issues detected")
        else:
            print(f"  Status: {result['message']}")
    
    print("\nDiagnostic completed.")


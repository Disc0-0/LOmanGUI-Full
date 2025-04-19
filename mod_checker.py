"""
Steam Workshop Mod Checker Module

This module provides functionality to check and manage Steam Workshop mods for Last Oasis.
It handles:
 - Fetching mod update times from Steam Workshop
 - Comparing current mod versions with saved versions
 - Identifying mods that need updates
 - Managing mod information in a JSON database

The module uses web scraping with rate limiting and retry mechanisms to avoid
being blocked by Steam's servers.
"""

import json
import time
import random
import logging
import os
from typing import Dict, List, Tuple, Optional, Any, Union
from datetime import datetime

import requests
from bs4 import BeautifulSoup

# Configure logger
logger = logging.getLogger("ModChecker")

# Set up default handler if none exists
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
# Constants
DEFAULT_TIMEOUT = 15  # seconds
MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 2  # seconds
RATE_LIMIT_DELAY = (1, 3)  # Random delay between (min, max) seconds
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15"
]

def save_json(json_file: str, data: Dict[str, Any]) -> bool:
    """
    Save a dictionary to a JSON file.
    
    Args:
        json_file: Path to the JSON file to write
        data: Dictionary data to save
        
    Returns:
        True if successful, False otherwise
    """
    logger.debug(f"Saving data to JSON file: {json_file}")
    
    try:
        # Create backup of existing file
        if os.path.exists(json_file):
            backup_file = f"{json_file}.bak"
            try:
                with open(json_file, 'r') as src, open(backup_file, 'w') as dst:
                    dst.write(src.read())
                logger.debug(f"Created backup file: {backup_file}")
            except Exception as e:
                logger.warning(f"Failed to create backup file: {e}")
        
        # Write the new data
        with open(json_file, 'w') as f:
            json.dump(data, f, indent=4)
            
        logger.debug(f"Successfully saved data to {json_file}")
        return True
        
    except PermissionError as e:
        logger.error(f"Permission denied when writing to {json_file}: {e}")
        return False
    except Exception as e:
        logger.error(f"Error saving data to {json_file}: {e}")
        return False


def read_json(json_file: str) -> Dict[str, str]:
    """
    Read a JSON file and return its contents as a dictionary.
    
    Args:
        json_file: Path to the JSON file to read
        
    Returns:
        Dictionary containing mod IDs and their last update times
        
    Raises:
        FileNotFoundError: If the JSON file doesn't exist
        json.JSONDecodeError: If the file contains invalid JSON
        PermissionError: If the file can't be accessed due to permissions
    """
    logger.debug(f"Reading JSON file: {json_file}")
    
    try:
        # Check if file exists
        if not os.path.exists(json_file):
            logger.warning(f"JSON file not found: {json_file}, creating empty file")
            with open(json_file, 'w') as f:
                json.dump({}, f)
            return {}
        
        # Read the file
        with open(json_file, 'r') as file:
            data = json.load(file)
            # Ensure we have a dictionary
            if not isinstance(data, dict):
                logger.warning(f"JSON file {json_file} did not contain a dictionary, got {type(data).__name__}. Returning empty dict.")
                return {}
                
            # Remove the 'mods' key if it exists (it's a string that should be in config.json, not here)
            if 'mods' in data and isinstance(data['mods'], str):
                logger.warning(f"Found 'mods' string key in {json_file}, removing it")
                data.pop('mods')
                
            logger.debug(f"Successfully read JSON file containing {len(data)} entries")
            return data
            
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in file {json_file}: {e}")
        logger.info("Creating backup of corrupted file and returning empty dictionary")
        
        # Backup the corrupted file
        try:
            backup_file = f"{json_file}.bak.{int(time.time())}"
            if os.path.exists(json_file) and os.path.getsize(json_file) > 0:
                with open(json_file, 'r') as src, open(backup_file, 'w') as dst:
                    dst.write(src.read())
                logger.info(f"Created backup of corrupted file: {backup_file}")
        except Exception as backup_err:
            logger.error(f"Failed to create backup: {backup_err}")
            
        return {}
        
    except PermissionError as e:
        logger.error(f"Permission denied when reading {json_file}: {e}")
        return {}
        
    except Exception as e:
        logger.error(f"Unexpected error reading {json_file}: {e}")
        return {}


def validate_mod_id(mod_id: str) -> bool:
    """
    Validate that a mod ID is in the correct format (numeric string).
    
    Args:
        mod_id: The mod ID to validate
        
    Returns:
        True if the mod ID is valid, False otherwise
    """
    if not mod_id:
        logger.warning("Empty mod ID provided")
        return False
        
    if not mod_id.strip().isdigit():
        logger.warning(f"Invalid mod ID format: {mod_id} (must be numeric)")
        return False
        
    return True


def fetch_mod_update_time(mod_id: str) -> Optional[str]:
    """
    Fetch the mod's last update time from Steam Workshop.
    
    Uses web scraping to extract the update date information from the mod's
    Steam Workshop page. Includes retry logic and rate limiting.
    
    Args:
        mod_id: The Steam Workshop ID of the mod
        
    Returns:
        The last update time as a string, or None if retrieval failed
    """
    if not validate_mod_id(mod_id):
        logger.error(f"Cannot fetch update time for invalid mod ID: {mod_id}")
        return None
        
    logger.info(f"Fetching update time for mod: {mod_id}")
    url = f"https://steamcommunity.com/sharedfiles/filedetails/?id={mod_id}"
    
    # Try multiple times with backoff
    for attempt in range(MAX_RETRIES):
        try:
            # Add rate limiting delay
            if attempt > 0:
                delay = random.uniform(RATE_LIMIT_DELAY[0], RATE_LIMIT_DELAY[1]) * RETRY_BACKOFF_FACTOR * attempt
                logger.debug(f"Rate limit delay: Waiting {delay:.2f} seconds before retry {attempt+1}/{MAX_RETRIES}")
                time.sleep(delay)
                
            # Use random user agent to avoid detection
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            
            # Make the request with timeout
            logger.debug(f"Sending request to: {url}")
            response = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
            
            # Check for successful response
            if response.status_code != 200:
                logger.warning(f"Received non-200 status code: {response.status_code} for mod {mod_id}")
                if response.status_code == 429:  # Too Many Requests
                    backoff_time = RETRY_BACKOFF_FACTOR * (attempt + 1) * 2
                    logger.warning(f"Rate limited by Steam (HTTP 429). Increasing backoff time to {backoff_time} seconds. "
                                   f"This usually happens when making too many requests in a short period.")
                    time.sleep(backoff_time)
                    continue
                elif 500 <= response.status_code < 600:  # Server error
                    backoff_time = RETRY_BACKOFF_FACTOR * (attempt + 1)
                    logger.warning(f"Steam server error: HTTP {response.status_code}. "
                                   f"This is likely a temporary issue with Steam's servers. "
                                   f"Waiting {backoff_time} seconds before retry.")
                    time.sleep(backoff_time)
                    continue
                
            # Parse HTML response
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try multiple selectors to find the update date
            # First try the dedicated update section
            update_section = soup.select_one('.detailsStatRight:contains("Update")')
            if update_section:
                logger.debug(f"Found update section: {update_section.text}")
                return update_section.text.strip()
                
            # Then try the stats container which usually has update info
            stats_container = soup.find('div', class_='detailsStatsContainerRight')
            if stats_container:
                logger.debug(f"Found stats container: {stats_container.text}")
                # Try to extract date from container text
                if 'Update:' in stats_container.text:
                    update_text = stats_container.text.split('Update:')[1].strip().split('\n')[0]
                    logger.debug(f"Extracted update date: {update_text}")
                    return update_text
                return stats_container.text.strip()
                
            # Last resort: try to find the date pattern in the page
            dates = soup.select('.workshopItemDetailsHeader + .detailsStatRight')
            for date in dates:
                logger.debug(f"Found potential date: {date.text}")
                if date.text and len(date.text.strip()) > 5:  # Basic validation for a date string
                    return date.text.strip()
            
            logger.warning(f"Could not find update time for mod {mod_id} using known selectors")
            return None
            
        except requests.Timeout:
            logger.warning(f"Request timed out for mod {mod_id} (attempt {attempt+1}/{MAX_RETRIES}). "
                          f"This could be due to slow internet connection or Steam's servers being busy.")
        except requests.ConnectionError:
            logger.warning(f"Connection error for mod {mod_id} (attempt {attempt+1}/{MAX_RETRIES}). "
                          f"Check your internet connection and ensure Steam's servers are accessible.")
        except requests.RequestException as e:
            logger.warning(f"Request failed for mod {mod_id}: {e} (attempt {attempt+1}/{MAX_RETRIES}). "
                          f"Will retry with increased delay.")
        except Exception as e:
            logger.error(f"Unexpected error fetching mod {mod_id}: {e}")
            break
    
    logger.error(f"Failed to fetch update time for mod {mod_id} after {MAX_RETRIES} attempts")
    return None

def update_mods_info(mods_info: Dict[str, str], mod_ids: List[str]) -> Tuple[List[str], Dict[str, str]]:
    """
    Check and update mods info based on current data from Steam Workshop.
    
    This function fetches the current update time for each mod from Steam Workshop,
    compares it with the stored update time, and identifies mods that need updating.
    
    Args:
        mods_info: Dictionary of mod IDs and their last known update times
        mod_ids: List of mod IDs to check for updates
        
    Returns:
        Tuple containing:
            - List of mod IDs that are out of date
            - Updated mods_info dictionary with current update times
    """
    # Validate inputs
    if not isinstance(mods_info, dict):
        logger.error(f"mods_info must be a dictionary, got {type(mods_info).__name__}")
        return [], {}
        
    if not isinstance(mod_ids, list):
        logger.error(f"mod_ids must be a list, got {type(mod_ids).__name__}")
        try:
            # Try to convert string to list if possible (e.g., comma-separated IDs)
            if isinstance(mod_ids, str):
                mod_ids = mod_ids.split(',')
                logger.warning(f"Converted mod_ids string to list: {mod_ids}")
            else:
                return [], mods_info
        except Exception as e:
            logger.error(f"Failed to convert mod_ids to list: {e}")
            return [], mods_info

    out_of_date = []
    total_mods = len(mod_ids)
    update_count = 0
    
    logger.info(f"Checking updates for {total_mods} mods")
    
    # Validate and filter mod IDs
    valid_mod_ids = [mod_id for mod_id in mod_ids if validate_mod_id(mod_id)]
    
    if len(valid_mod_ids) != total_mods:
        logger.warning(f"Filtered out {total_mods - len(valid_mod_ids)} invalid mod IDs")
        
    # Update progress counter
    processed = 0
        
    for mod_id in valid_mod_ids:
        processed += 1
        mod_id = mod_id.strip()  # Ensure no whitespace
        
        # Add rate limiting to avoid being blocked by Steam
        if processed > 1:  # Don't delay the first request
            delay = random.uniform(RATE_LIMIT_DELAY[0], RATE_LIMIT_DELAY[1])
            logger.debug(f"Rate limiting: waiting {delay:.2f} seconds before next request")
            time.sleep(delay)
            
        logger.info(f"Processing mod {processed}/{len(valid_mod_ids)}: {mod_id}")
        
        # Fetch current update time from Steam
        current_time = fetch_mod_update_time(mod_id)
        
        # Skip if we couldn't fetch the update time
        if current_time is None:
            logger.warning(f"Couldn't fetch update time for mod {mod_id}, skipping update check")
            continue
            
        # Check if mod exists in our info and if it's out of date
        if mod_id in mods_info:
            saved_time = mods_info[mod_id]
            
            # Skip comparison if saved_time is None (new mod)
            if saved_time is None:
                logger.info(f"Mod {mod_id} is new, setting initial update time to: {current_time}")
                mods_info[mod_id] = current_time
                continue
            
            # Handle the case where saved_time might be a dictionary (legacy format)
            if isinstance(saved_time, dict):
                logger.warning(f"Found dictionary format for mod {mod_id}, converting to string format")
                # Try to extract the update time from the dictionary if possible
                try:
                    if 'update_time' in saved_time:
                        saved_time = str(saved_time['update_time'])
                    else:
                        # If we can't find update time, treat as new mod
                        logger.warning(f"Couldn't find update time in dictionary for mod {mod_id}")
                        mods_info[mod_id] = current_time
                        continue
                except Exception as e:
                    logger.error(f"Error converting dictionary to string for mod {mod_id}: {e}")
                    mods_info[mod_id] = current_time
                    continue
            
            # Compare update times - both should be strings now
            try:
                # Extract update date from multi-line format if needed
                saved_update_date = saved_time
                if '\n' in saved_time:
                    # Format is "size\ncreation date\nupdate date"
                    parts = saved_time.split('\n')
                    if len(parts) >= 3:
                        saved_update_date = parts[2]  # Third line is update date
                    
                # Extract update date from current_time if it's multi-line
                current_update_date = current_time
                if '\n' in current_time:
                    parts = current_time.split('\n')
                    if len(parts) >= 3:
                        current_update_date = parts[2]  # Third line is update date
                
                if saved_update_date != current_update_date:
                    logger.info(f"Mod {mod_id} is out of date!")
                    logger.debug(f"  Saved time: {saved_update_date}")
                    logger.debug(f"  Current time: {current_update_date}")
                    out_of_date.append(mod_id)
                    mods_info[mod_id] = current_time  # Update the recorded last update time
                    update_count += 1
                else:
                    logger.debug(f"Mod {mod_id} is up to date")
            except Exception as e:
                logger.error(f"Error comparing update times for mod {mod_id}: {e}")
                # Continue processing other mods even if this one fails
        else:
            # Mod not in our database, add it
            logger.info(f"Adding new mod {mod_id} with update time: {current_time}")
            mods_info[mod_id] = current_time  # Add new mod to the dictionary
            
    logger.info(f"Update check complete: {update_count} mods need updates")
    if out_of_date:
        logger.info(f"Out-of-date mods: {', '.join(out_of_date)}")

    return out_of_date, mods_info


def add_new_mod_ids(mods_info: Dict[str, str], new_mod_ids: Union[List[str], str]) -> Dict[str, str]:
    """
    Add new mod IDs to the mods info dictionary if they aren't already present.
    
    Args:
        mods_info: Dictionary of mod IDs and their last update times
        new_mod_ids: List of new mod IDs to add, or a single mod ID as string
        
    Returns:
        Updated mods_info dictionary with new mod IDs added
    """
    # Validate inputs
    if not isinstance(mods_info, dict):
        logger.error(f"mods_info must be a dictionary, got {type(mods_info).__name__}")
        return {}
    
    # Handle different input types for new_mod_ids
    if isinstance(new_mod_ids, str):
        # Check if it's a single mod ID or a comma-delimited string
        if ',' in new_mod_ids:
            # Handle comma-delimited string
            logger.debug("Converting comma-delimited string to list of mod IDs")
            new_mod_ids = [mod_id.strip() for mod_id in new_mod_ids.split(',') if mod_id.strip()]
        else:
            # It's a single mod ID
            single_id = new_mod_ids.strip()
            if single_id:
                logger.debug(f"Converting single mod ID string '{single_id}' to list")
                new_mod_ids = [single_id]
            else:
                logger.warning("Empty mod ID string provided")
                new_mod_ids = []
    elif not isinstance(new_mod_ids, list):
        logger.error(f"new_mod_ids must be a list or string, got {type(new_mod_ids).__name__}")
        return mods_info
    
    # Additional validation: ensure all items in the list are non-empty strings
    if isinstance(new_mod_ids, list):
        # Filter out any non-string or empty items
        valid_mod_ids = []
        for item in new_mod_ids:
            if not isinstance(item, str):
                logger.warning(f"Skipping non-string item in mod_ids list: {item}")
                continue
            if not item.strip():
                logger.warning("Skipping empty string in mod_ids list")
                continue
            valid_mod_ids.append(item.strip())
            
        if len(valid_mod_ids) != len(new_mod_ids):
            logger.warning(f"Filtered {len(new_mod_ids) - len(valid_mod_ids)} invalid items from mod_ids list")
            
        new_mod_ids = valid_mod_ids
    
    added_count = 0
    skipped_count = 0
    
    logger.info(f"Adding {len(new_mod_ids)} new mod IDs to the database")
    
    for mod_id in new_mod_ids:
        mod_id = mod_id.strip()
        
        # Validate the mod ID
        if not validate_mod_id(mod_id):
            logger.warning(f"Skipping invalid mod ID: {mod_id}")
            skipped_count += 1
            continue
            
        # Check if it's already in the database
        if mod_id in mods_info:
            logger.debug(f"Mod ID {mod_id} already exists in database, skipping")
            skipped_count += 1
            continue
            
        try:
            # Add the new mod ID with None as placeholder for update time
            logger.info(f"Adding new mod ID: {mod_id}")
            mods_info[mod_id] = None  # Initialize with None, will be updated during next check
            added_count += 1
        except Exception as e:
            logger.error(f"Error adding mod ID {mod_id}: {e}")
    
    logger.info(f"Added {added_count} new mod IDs, skipped {skipped_count}")
    return mods_info

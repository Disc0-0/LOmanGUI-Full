import os
import time
import re
import json
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from TileTracker import get_tracker

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='log_monitor.log',
    filemode='a'
)
logger = logging.getLogger('LogMonitor')


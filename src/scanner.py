import os
import re
from .config import MONTH_FOLDER_PATTERN, SUPPORTED_EXTENSIONS

def is_valid_month_folder(folder_name):
    """Checks if a folder name matches the expected monthly pattern."""
    return bool(re.match(MONTH_FOLDER_PATTERN, folder_name, re.IGNORECASE))

def scan_folders(base_path):
    """
    Scans the base path for valid month folders and their supported files.
    Returns a dictionary mapping month (e.g. '01') to a list of file paths.
    """
    if not os.path.exists(base_path):
        raise ValueError(f"Base path does not exist or is not accessible. Please check if the drive is mounted and the path is correct:\n{base_path}")
        
    results = {}
    
    # List and filter directories
    for item in os.listdir(base_path):
        item_path = os.path.join(base_path, item)
        if os.path.isdir(item_path) and is_valid_month_folder(item):
            # Extract month number, e.g. "01" from "01 - JANEIRO"
            match = re.search(r"^(0[1-9]|1[0-2])", item)
            if match:
                month_num = match.group(1)
                
                # Scan for files
                files = []
                for root, _, filenames in os.walk(item_path):
                    for filename in filenames:
                        ext = os.path.splitext(filename)[1].lower()
                        if ext in SUPPORTED_EXTENSIONS:
                            files.append(os.path.join(root, filename))
                            
                results[month_num] = {
                    "folder_name": item,
                    "folder_path": item_path,
                    "files": files
                }
                
    # Sort results by month number ascending
    return dict(sorted(results.items()))

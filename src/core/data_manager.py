#!/usr/bin/env python3
import json
import os
from pathlib import Path
from typing import Dict, Optional


class DataManager:
    """Handles loading and saving of JSON data files."""

    def __init__(self, data_folder: str = "data"):
        self.data_folder = Path(data_folder)
        self.data_folder.mkdir(exist_ok=True)

        self.database_file = self.data_folder / "database.json"
        self.search_data_file = self.data_folder / "search_data.json"

    def initialize_files(self, enabled_sites: list) -> bool:
        """Create database files if they don't exist."""
        try:
            # Initialize search data structure
            empty_search_data = {}
            for tracker in enabled_sites:
                empty_search_data[tracker] = {
                    "safe": {},
                    "risky": {},
                    "danger": {},
                }

            # Create files with default data if they don't exist
            files_to_create = [
                (self.database_file, {}),
                (self.search_data_file, empty_search_data),
            ]

            for file_path, default_data in files_to_create:
                if not file_path.exists():
                    with open(file_path, "w", encoding="utf-8") as outfile:
                        json.dump(default_data, outfile, ensure_ascii=False, indent=2)

            return True
        except Exception as e:
            print(f"Error initializing JSON files: {e}")
            return False

    def load_scan_data(self) -> Dict:
        """Load scan data from database.json."""
        try:
            if (self.database_file.exists() and 
                self.database_file.stat().st_size > 10):
                with open(self.database_file, "r", encoding="utf-8") as file:
                    return json.load(file)
            return {}
        except Exception as e:
            print(f"Error loading scan data: {e}")
            return {}

    def load_search_data(self) -> Dict:
        """Load search data from search_data.json."""
        try:
            if (self.search_data_file.exists() and 
                self.search_data_file.stat().st_size > 10):
                with open(self.search_data_file, "r", encoding="utf-8") as file:
                    return json.load(file)
            return {}
        except Exception as e:
            print(f"Error loading search data: {e}")
            return {}

    def save_scan_data(self, scan_data: Dict) -> bool:
        """Save scan data to database.json."""
        try:
            with open(self.database_file, "w", encoding="utf-8") as file:
                json.dump(scan_data, file, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Error saving scan data to database.json: {e}")
            return False

    def save_search_data(self, search_data: Dict) -> bool:
        """Save search data to search_data.json."""
        try:
            with open(self.search_data_file, "w", encoding="utf-8") as file:
                json.dump(search_data, file, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Error saving search data to search_data.json: {e}")
            return False

    def clear_all_data(self, enabled_sites: list) -> bool:
        """Clear all stored data from JSON files."""
        try:
            # Clear search data with proper structure
            empty_search_data = {}
            for tracker in enabled_sites:
                empty_search_data[tracker] = {
                    "safe": {},
                    "risky": {},
                    "danger": {},
                }

            # Write empty data to files
            with open(self.search_data_file, "w", encoding="utf-8") as file:
                json.dump(empty_search_data, file, ensure_ascii=False, indent=2)

            with open(self.database_file, "w", encoding="utf-8") as file:
                json.dump({}, file, indent=2)

            print("Data cleared!")
            return True
        except Exception as e:
            print(f"Error clearing JSON data: {e}")
            return False

    def get_database_path(self) -> str:
        """Get the path to the database file."""
        return str(self.database_file)

    def get_search_data_path(self) -> str:
        """Get the path to the search data file."""
        return str(self.search_data_file)

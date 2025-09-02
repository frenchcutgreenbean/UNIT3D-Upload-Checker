#!/usr/bin/env python3
"""
UNIT3D Upload Checker - Clean, refactored version.
Main orchestrator class that coordinates all specialized components.
"""
import math
from typing import Dict, List, Optional

from .core import (
    FileScanner, 
    TMDBMatcher, 
    TrackerSearcher,
    SearchDataProcessor,
    ResultExporter,
    DataManager
)
from .settings import Settings


class UploadChecker:
    """
    Main orchestrator class that coordinates all components.
    Provides a clean interface to the complete workflow.
    """
    
    def __init__(self):
        # Initialize settings first
        self.settings = Settings()
        self._update_settings()
        
        # Initialize data manager
        self.data_manager = DataManager()
        self.data_manager.initialize_files(self.enabled_sites)
        
        # Initialize core components
        self.file_scanner = FileScanner()
        self.tmdb_matcher = TMDBMatcher(self.tmdb_key) if self.tmdb_key else None
        self.tracker_searcher = TrackerSearcher(self.tracker_info, self.settings)
        self.search_processor = SearchDataProcessor(self.tmdb_matcher, self.settings)
        self.result_exporter = ResultExporter("outputs/", self.tracker_info, self.settings)
        
        # Load existing data
        self.scan_data = self.data_manager.load_scan_data()
        self.search_data = self.data_manager.load_search_data()

    def scan_directories(self, verbose: bool = False) -> bool:
        """Scan configured directories for media files."""
        try:
            if not self.directories:
                print("Please add a directory")
                print("add dir <dir>")
                return False
                
            success = self.file_scanner.scan_directories(self.directories, verbose)
            
            if success:
                new_scan_data = self.file_scanner.get_scan_data()
                
                # Preserve existing TMDB and tracker data when rescanning
                self.scan_data = self._merge_scan_data(self.scan_data, new_scan_data, verbose)
                self.save_database()
                
            return success
        except Exception as e:
            print(f"Error in scan_directories: {e}")
            return False

    def _merge_scan_data(self, existing_data: Dict, new_data: Dict, verbose: bool = False) -> Dict:
        """Merge new scan data with existing data, preserving TMDB and tracker information."""
        merged_data = new_data.copy()  # Start with new scan data
        
        preserved_count = 0
        
        for directory, files in existing_data.items():
            if directory not in merged_data:
                # Directory no longer exists, skip it
                if verbose:
                    print(f"  📁 Directory removed: {directory}")
                continue
                
            for filename, file_info in files.items():
                if filename in merged_data[directory]:
                    # File still exists, preserve important data
                    new_file_info = merged_data[directory][filename]
                    
                    # Preserve TMDB data
                    tmdb_fields = ["tmdb", "tmdb_title", "tmdb_year", "tmdb_match_score", "tmdb_match_info"]
                    for field in tmdb_fields:
                        if field in file_info and file_info[field]:
                            new_file_info[field] = file_info[field]
                    
                    # Preserve tracker data
                    if "trackers" in file_info:
                        new_file_info["trackers"] = file_info["trackers"]
                    
                    # Preserve ban status and media info
                    if "banned" in file_info:
                        new_file_info["banned"] = file_info["banned"]
                    if "media_info" in file_info:
                        new_file_info["media_info"] = file_info["media_info"]
                    
                    preserved_count += 1
                elif verbose:
                    print(f"  📄 File removed: {filename}")
        
        if verbose and preserved_count > 0:
            print(f"  ✓ Preserved data for {preserved_count} existing files")
            
        return merged_data

    def get_tmdb(self, verbose: bool = False) -> bool:
        """Search TMDB for all scanned files."""
        if not self.tmdb_matcher:
            print("Please add a TMDB key")
            print("add tmdb <key>")
            return False
            
        try:
            # Create a callback to save progress after each file
            def save_progress_callback(scan_data):
                """Save current scan data progress."""
                self.scan_data = scan_data  # Update our reference
                self.save_database()
            
            success = self.tmdb_matcher.search_tmdb_for_files(
                self.scan_data, 
                verbose, 
                save_progress_callback
            )
            
            # Final save (though should already be saved by callback)
            if success:
                self.save_database()
                
            return success
        except Exception as e:
            print(f"Error in get_tmdb: {e}")
            return False

    def search_trackers(self, verbose: bool = False) -> bool:
        """Search all enabled trackers for files."""
        try:
            # Create a callback to save progress after each file
            def save_progress_callback(scan_data):
                """Save current scan data progress."""
                self.scan_data = scan_data  # Update our reference
                self.save_database()
            
            success = self.tracker_searcher.search_trackers(
                self.scan_data, 
                self.enabled_sites, 
                self.cooldown, 
                verbose,
                save_progress_callback
            )
            
            # Final save (though should already be saved by callback)
            if success:
                self.save_database()
                
            return success
        except Exception as e:
            print(f"Error in search_trackers: {e}")
            return False

    def create_search_data(self, verbose: bool = False) -> bool:
        """Create search data by processing scan results and categorizing by safety level."""
        try:
            self.search_data = self.search_processor.create_search_data(
                self.scan_data, 
                self.enabled_sites,
                verbose
            )
            
            self.save_database()
            self.save_search_data()
            return True
        except Exception as e:
            print(f"Error in create_search_data: {e}")
            return False

    def export_gg(self) -> bool:
        """Export gg-bot commands."""
        return self.result_exporter.export_gg_commands(self.search_data)

    def export_ua(self) -> bool:
        """Export Upload Assistant commands."""
        return self.result_exporter.export_ua_commands(self.search_data)

    def export_txt(self) -> bool:
        """Export manual text format."""
        return self.result_exporter.export_txt_format(self.search_data)

    def export_csv(self) -> bool:
        """Export CSV format."""
        return self.result_exporter.export_csv_format(self.search_data)

    def run_all(self, verbose: bool = False) -> bool:
        """Run the complete workflow: scan -> tmdb -> search -> create data -> export."""
        try:
            print("Starting complete workflow...")

            # Step 1: Scan directories
            print("\n--- Step 1: Scanning Directories ---")
            if not self.scan_directories(verbose):
                print("Directory scanning failed. Aborting.")
                return False

            # Step 2: Get TMDB data
            print("\n--- Step 2: Getting TMDB Data ---")
            if not self.get_tmdb(verbose):
                print("TMDB search failed. Aborting.")
                return False

            # Step 3: Search trackers
            print("\n--- Step 3: Searching Trackers ---")
            if not self.search_trackers(verbose):
                print("Tracker search failed. Aborting.")
                return False

            # Step 4: Create search data
            print("\n--- Step 4: Creating Search Data ---")
            if not self.create_search_data(verbose):
                print("Creating search data failed. Aborting.")
                return False

            # Step 5: Export all formats
            print("\n--- Step 5: Exporting Results ---")
            self.export_gg()
            self.export_ua()
            self.export_txt()
            self.export_csv()

            print("\nComplete workflow finished successfully!")
            return True

        except Exception as e:
            print(f"Error in run_all workflow: {e}")
            return False

    # Data persistence methods
    def save_database(self) -> bool:
        """Save scan data to database.json."""
        return self.data_manager.save_scan_data(self.scan_data)

    def save_search_data(self) -> bool:
        """Save search data to search_data.json."""
        return self.data_manager.save_search_data(self.search_data)

    def clear_data(self) -> bool:
        """Clear all stored data from JSON files."""
        success = self.data_manager.clear_all_data(self.enabled_sites)
        if success:
            self.scan_data = {}
            self.search_data = {tracker: {"safe": {}, "risky": {}, "danger": {}} 
                              for tracker in self.enabled_sites}
        return success

    # Settings management methods
    def update_setting(self, target: str, value) -> None:
        """Update a specific setting."""
        self.settings.update_setting(target, value)
        self._update_settings()
        
        # Reinitialize components that depend on settings
        if target == "tmdb_key":
            self.tmdb_matcher = TMDBMatcher(self.tmdb_key) if self.tmdb_key else None
            self.search_processor = SearchDataProcessor(self.tmdb_matcher, self.settings)

    def get_setting(self, target: str) -> None:
        """Get and print a specific setting."""
        setting = self.settings.return_setting(target)
        if setting is not None:
            print(setting)
        else:
            print("Not set yet.")

    def reset_setting(self) -> None:
        """Reset all settings to defaults."""
        self.settings.reset_settings()
        self._update_settings()

    def remove_setting(self, target: str) -> None:
        """Remove a specific setting."""
        self.settings.remove_setting(target)
        self._update_settings()

    def update_settings(self) -> None:
        """Legacy method name - delegates to private method."""
        self._update_settings()

    def _update_settings(self) -> None:
        """Update instance attributes from settings."""
        self.current_settings = self.settings.current_settings
        self.directories = self.current_settings.get("directories", [])
        self.tmdb_key = self.current_settings.get("tmdb_key", "")
        self.enabled_sites = self.current_settings.get("enabled_sites", [])
        self.cooldown = self.current_settings.get("search_cooldown", 5)
        self.minimum_size = self.current_settings.get("min_file_size", 0)
        self.ignore_qualities = self.current_settings.get("ignored_qualities", [])
        self.ignore_keywords = self.current_settings.get("ignored_keywords", [])
        self.gg_path = self.current_settings.get("gg_path", "")
        self.ua_path = self.current_settings.get("ua_path", "")
        self.tracker_info = self.settings.tracker_info

    # Utility methods
    @staticmethod
    def convert_size(size_bytes: int) -> str:
        """Convert bytes to human readable format."""
        if size_bytes == 0:
            return "0B"
        size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_name[i]}"
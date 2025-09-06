#!/usr/bin/env python3
"""
UNIT3D Upload Checker - Clean, refactored version.
Main orchestrator class that coordinates all specialized components.
"""
import math
import traceback
from typing import Dict

from .core import (
    FileScanner,
    TMDBMatcher,
    TrackerSearcher,
    SearchDataProcessor,
    ResultExporter,
    DataManager,
    FileScreener,
)
from .settings import Settings
from .utils.logger import get_logger, logger

logger = get_logger()


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
        self.file_screener = FileScreener(self.settings, self.tmdb_matcher)
        self.tracker_searcher = TrackerSearcher(self.tracker_info, self.settings)
        self.search_processor = SearchDataProcessor(self.tmdb_matcher, self.settings)
        self.result_exporter = ResultExporter(
            "outputs/", self.tracker_info, self.settings
        )

        # Load existing data
        self.scan_data = self.data_manager.load_scan_data()
        self.search_data = self.data_manager.load_search_data()

    def scan_directories(self, verbose: bool = False) -> bool:
        """Scan configured directories for media files."""
        try:
            if not self.directories:
                logger.error("No directories configured")
                logger.info("Use: python uploadchecker.py add dir <directory_path>")
                return False

            success = self.file_scanner.scan_directories(self.directories, verbose)

            if success:
                new_scan_data = self.file_scanner.get_scan_data()

                # Preserve existing TMDB and tracker data when rescanning
                self.scan_data = self._merge_scan_data(
                    self.scan_data, new_scan_data, verbose
                )
                self.save_database()

            return success
        except Exception as e:
            logger.error(f"Error in scan_directories: {e}")
            logger.debug(traceback.format_exc())
            return False

    @staticmethod
    def _merge_scan_data(
        existing_data: Dict, new_data: Dict, verbose: bool = False
    ) -> Dict:
        """Merge new scan data with existing data, preserving TMDB and tracker information."""
        merged_data = new_data.copy()  # Start with new scan data

        preserved_count = 0

        for directory, files in existing_data.items():
            if directory not in merged_data:
                # Directory no longer exists, skip it
                if verbose:
                    logger.info(f"  📁 Directory removed: {directory}")
                continue

            for filename, file_info in files.items():
                if filename in merged_data[directory]:
                    # File still exists, preserve important data
                    new_file_info = merged_data[directory][filename]

                    # Preserve TMDB data
                    tmdb_fields = [
                        "tmdb",
                        "tmdb_title",
                        "tmdb_year",
                        "tmdb_match_score",
                        "tmdb_match_info",
                    ]
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
                    logger.info(f"  📄 File removed: {filename}")

        if verbose and preserved_count > 0:
            logger.info(f"  ✓ Preserved data for {preserved_count} existing files")

        return merged_data

    def get_tmdb(self, verbose: bool = False) -> bool:
        """Search TMDB for all scanned files."""
        if not self.tmdb_matcher:
            logger.error("No TMDB API key configured")
            logger.info("Use: python uploadchecker.py add tmdb YOUR_API_KEY")
            return False

        try:
            # Create a callback to save progress after each file
            def save_progress_callback(scan_data):
                """Save current scan data progress."""
                self.scan_data = scan_data  # Update our reference
                self.save_database()

            success = self.tmdb_matcher.search_tmdb_for_files(
                self.scan_data, verbose, save_progress_callback
            )

            # Final save (though should already be saved by callback)
            if success:
                self.save_database()

            return success
        except Exception as e:
            logger.error(f"Error in get_tmdb: {e}")
            logger.debug(traceback.format_exc())
            return False

    def screen_files(self, verbose: bool = False) -> bool:
        """
        Screen files for obvious issues after TMDB matching but before API calls.
        This also extracts media info for files that pass basic screening.
        """
        try:
            logger.section("Screening Files")
            if verbose:
                logger.info("Screening files and extracting media info...")

            # Track statistics
            stats = {"total": 0, "screened": 0, "banned": 0}

            # Process each file
            for directory in self.scan_data:
                for file_name, file_data in list(self.scan_data[directory].items()):
                    stats["total"] += 1

                    # Skip already banned files
                    if file_data.get("banned", False):
                        if verbose:
                            logger.debug(f"  ⏭️ Skipping already banned: {file_name}")
                        continue

                    # Skip files without TMDB match
                    if not file_data.get("tmdb"):
                        if verbose:
                            logger.debug(f"  ⏭️ Skipping (no TMDB match): {file_name}")
                        continue

                    # Screen file
                    is_safe, reason, updated_file_data = self.file_screener.screen_file(
                        file_data, verbose
                    )
                    stats["screened"] += 1

                    # Update file data with media info
                    self.scan_data[directory][file_name] = updated_file_data

                    # Ban files that fail screening
                    if not is_safe:
                        if verbose:
                            logger.warning(f"Banned: {file_name} - {reason}")
                        self.scan_data[directory][file_name]["banned"] = True
                        self.scan_data[directory][file_name]["banned_reason"] = reason
                        stats["banned"] += 1

            if verbose:
                logger.section("File Screening Summary")
                logger.info(f"✓ Total files: {stats['total']}")
                logger.info(f"Files screened: {stats['screened']}")
                logger.info(f"Files banned: {stats['banned']}")

            # Save updated scan data
            self.save_database()
            return True

        except Exception as e:
            logger.error(f"Error in screen_files: {e}")
            logger.debug(traceback.format_exc())
            if verbose:
                traceback.print_exc()
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
                save_progress_callback,
            )

            # Final save (though should already be saved by callback)
            if success:
                self.save_database()

            return success
        except Exception as e:
            logger.error(f"Error in search_trackers: {e}")
            logger.debug(traceback.format_exc())
            return False

    def create_search_data(self, verbose: bool = False) -> bool:
        """Create search data by processing scan results and categorizing by safety level."""
        try:
            self.search_data = self.search_processor.create_search_data(
                self.scan_data, self.enabled_sites, verbose
            )

            self.save_database()
            self.save_search_data()
            return True
        except Exception as e:
            logger.error(f"Error in create_search_data: {e}")
            logger.debug(traceback.format_exc())
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
            logger.info("Starting complete workflow...")

            # Step 1: Scan directories
            logger.section("Step 1: Scanning Directories")
            if not self.scan_directories(verbose):
                logger.error("Directory scanning failed. Aborting.")
                return False

            # Step 2: Get TMDB data
            logger.section("Step 2: Getting TMDB Data")
            if not self.get_tmdb(verbose):
                logger.error("TMDB search failed. Aborting.")
                return False

            # Step 3: Screen files and extract media info
            logger.section("Step 3: Screening Files and Extracting Media Info")
            if not self.screen_files(verbose):
                logger.error("File screening failed. Aborting.")
                return False

            # Step 4: Search trackers
            logger.section("Step 4: Searching Trackers")
            if not self.search_trackers(verbose):
                logger.error("Tracker search failed. Aborting.")
                return False

            # Step 5: Create search data
            logger.section("Step 5: Creating Search Data")
            if not self.create_search_data(verbose):
                logger.error("Creating search data failed. Aborting.")
                return False

            # Step 6: Export all formats
            logger.section("Step 6: Exporting Results")
            if not self.settings.current_settings.get("gg_path"):
                logger.warning("No gg_path configured, skipping gg-bot export.")
            else:
                self.export_gg()
            if not self.settings.current_settings.get("ua_path"):
                logger.warning(
                    "No ua_path configured, skipping Upload Assistant export."
                )
            else:
                self.export_ua()
            self.export_txt()
            self.export_csv()

            logger.success("Complete workflow finished successfully!")
            return True

        except Exception as e:
            logger.error(f"Error in run_all workflow: {e}")
            logger.debug(traceback.format_exc())
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
            self.search_data = {
                tracker: {"safe": {}, "risky": {}} for tracker in self.enabled_sites
            }
        return success

    # Settings management methods
    def update_setting(self, target: str, value) -> None:
        """Update a specific setting."""
        self.settings.update_setting(target, value)
        self._update_settings()

        # Reinitialize components that depend on settings
        if target == "tmdb_key":
            self.tmdb_matcher = TMDBMatcher(self.tmdb_key) if self.tmdb_key else None
            self.search_processor = SearchDataProcessor(
                self.tmdb_matcher, self.settings
            )

    def get_setting(self, target: str) -> None:
        """Get and print a specific setting."""
        setting = self.settings.return_setting(target)
        if setting is not None:
            logger.info(setting)
        else:
            logger.warning("Not set yet.")

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
        """Convert bytes to human-readable format."""
        if size_bytes == 0:
            return "0B"
        size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_name[i]}"

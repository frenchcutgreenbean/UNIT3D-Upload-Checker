#!/usr/bin/env python3
import time
import traceback
from typing import Dict, List

from ..trackers.adapter import get_tracker_driver
from ..utils.logger import get_logger

# Initialize logger
logger = get_logger()


class TrackerSearcher:
    """Handles searching across multiple trackers for duplicate content."""

    def __init__(self, tracker_info: Dict, settings_manager):
        self.tracker_info = tracker_info
        self.settings = settings_manager

    def search_trackers(
        self,
        scan_data: Dict,
        enabled_sites: List[str],
        cooldown: int = 5,
        verbose: bool = False,
        save_callback: callable = None,
    ) -> bool:
        """Search all enabled trackers for files in scan data."""
        try:
            logger.section("Searching Trackers")
            logger.info("Searching trackers for duplicates")

            if not self._validate_api_keys(enabled_sites):
                return False

            # Count total files for progress tracking
            total_files = 0
            for directory in scan_data:
                for file_name, file_data in scan_data[directory].items():
                    if self._should_process_file(file_data):
                        total_files += 1

            processed_count = 0
            logger.info(f"Found {total_files} files to process")

            for directory in scan_data:
                for file_name, file_data in scan_data[directory].items():
                    if verbose and file_data.get("banned"):
                        logger.debug(f"Banned file check: {file_data.get('banned')}")
                    if not self._should_process_file(file_data):
                        continue
                    if verbose and file_data.get("banned"):
                        logger.debug("process_file broken - file marked as banned but still processed")
                    processed_count += 1
                    progress = (
                        (processed_count / total_files) * 100 if total_files > 0 else 0
                    )
                    logger.info(f"\n[{processed_count}/{total_files} - {progress:.1f}%]")

                    self._search_file_on_trackers(
                        file_data, enabled_sites, cooldown, verbose
                    )

                    # Save progress after each file
                    if save_callback:
                        try:
                            save_callback(scan_data)
                            if verbose:
                                logger.debug(
                                    f"💾 Progress saved after processing '{file_data['title']}'"
                                )
                        except Exception as e:
                            logger.warning(f"Failed to save progress: {e}")

            logger.success(f"Tracker search completed! Processed {processed_count} files.")
            return True
        except Exception as e:
            logger.error(f"Error searching trackers: {e}")
            logger.debug(traceback.format_exc())
            return False

    def _validate_api_keys(self, enabled_sites: List[str]) -> bool:
        """Validate that all enabled trackers have API keys."""
        api_keys = (getattr(self.settings, "current_settings", {}) or {}).get(
            "keys", {}
        ) or {}

        for tracker in enabled_sites:
            if not api_keys.get(tracker):
                logger.warning(f"No API key for {tracker} found.")
                logger.info(
                    "If you want to use this tracker, add an API key to the settings."
                )
                if not input("Continue? [y/n] ").lower().startswith("y"):
                    return False
        return True

    @staticmethod
    def _should_process_file(file_data: Dict) -> bool:
        """Check if file should be processed for tracker searches."""
        if file_data.get("banned", False):
            return False
        if file_data.get("tmdb") is None:
            return False
        return True

    def _search_file_on_trackers(
        self,
        file_data: Dict,
        enabled_sites: List[str],
        cooldown: int,
        verbose: bool = False,
    ):
        """Search a single file across all enabled trackers."""
        logger.debug("=" * 80)
        logger.info(f"Searching Trackers for {file_data['title']}")

        if verbose:
            logger.debug(f"File: {file_data.get('file_name')}")

        if "trackers" not in file_data:
            file_data["trackers"] = {}
            
        # Track whether we actually made any API calls
        api_calls_made = False

        for tracker in enabled_sites:
            try:
                # Get the tracker's info from tracker_info.json
                tracker_info = self.tracker_info.get(tracker, {})

                if not tracker_info:
                    logger.warning(f"Tracker {tracker} not found in tracker_info.json")
                    continue

                # Create the appropriate tracker driver
                driver = get_tracker_driver(tracker, tracker_info, self.settings)

                # Skip if already searched
                if tracker in file_data.get("trackers", {}):
                    if verbose:
                        logger.debug(
                            f"{tracker} already searched for {file_data['title']}. Skipping."
                        )
                    continue

                # Search the tracker
                logger.info(f"Searching {tracker} for {file_data['title']}")
                result = driver.search_tracker(file_data, verbose)

                # Save result
                file_data["trackers"][tracker] = result

                # Print result
                self._print_tracker_result(tracker, result)
                
                # Mark that we made an API call
                api_calls_made = True
            except Exception as e:
                logger.error(f"Error searching {tracker} for {file_data['title']}: {str(e)}")
                logger.debug(traceback.format_exc())
                file_data["trackers"][tracker] = {
                    "exists_on_tracker": False,
                    "is_upgrade": False,
                    "upgrade_reason": None,
                    "errors": [f"Error: {str(e)}"],
                }
                
                # Count errors as API calls since we likely attempted a request
                api_calls_made = True

        # Only apply cooldown if we actually made API calls
        if api_calls_made:
            logger.info(f"Waiting for cooldown... {cooldown} seconds")
            time.sleep(cooldown)
        else:
            logger.info("No new tracker searches performed, skipping cooldown.")

    @staticmethod
    def _print_tracker_result(tracker: str, result: Dict):
        """Print the result of a tracker search."""
        if result.get("no_api_key", False):
            logger.warning(f"{tracker}: No API key")
        elif result.get("banned_group", False):
            logger.warning(f"{tracker}: Banned group")
        elif result.get("errors"):
            logger.error(
                f"{tracker}: Error - {result.get('errors')[0] if result.get('errors') else 'Unknown error'}"
            )
        elif result.get("is_duplicate", False):
            logger.warning(f"{tracker}: DUPLICATE - {result.get('duplicate_reason', 'Duplicate exists')}")
        elif result.get("exists_on_tracker", False):
            reason = result.get("upgrade_reason", "")
                    
            if result.get("is_upgrade", False):
                logger.success(f"{tracker}: SAFE - This is an upgrade over {reason}")
            else:
                logger.warning(f"{tracker}: RISKY - Similar quality exists: {reason}")
        else:
            logger.success(f"{tracker}: SAFE - Not found on tracker")

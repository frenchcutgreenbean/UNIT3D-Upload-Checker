#!/usr/bin/env python3
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

from src.utils.logger import logger
from src.utils.slot_checker import SlotChecker


class BaseTracker(ABC):
    """Abstract base class for all tracker API integrations."""

    def __init__(self, tracker: str, tracker_info: Dict, settings_manager):
        """
        Initialize the tracker API client.
        
        Args:
            tracker: Tracker identifier (e.g., 'beyondhd', 'blutopia')
            tracker_info: The tracker's configuration from tracker_info.json
            settings_manager: The settings manager instance with API keys, etc.
        """
        self.tracker = tracker
        self.tracker_info = tracker_info
        self.settings = settings_manager
        self.api_keys = (getattr(self.settings, "current_settings", {}) or {}).get("keys", {}) or {}
        self.api_key = self.api_keys.get(tracker)
        self.hq_webrip_groups =  self.settings.HQ_WEBRIP_GROUPS
        self.slot_checker = SlotChecker()
    @abstractmethod
    def search_tracker(self, file_data: Dict, verbose: bool = False) -> Dict:
        """
        Search the tracker for a file using TMDB ID.
        
        Args:
            file_data: File data dictionary with title, TMDB ID, etc.
            verbose: Whether to print verbose output
            
        Returns:
            Dict with structured search result
        """
        pass

    @abstractmethod
    def build_query(self, file_data: Dict) -> Dict:
        """
        Build the query parameters for the tracker API based on file data.
        
        Args:
            file_data: File data dictionary
            
        Returns:
            Dict with query parameters
        """
        pass

    @abstractmethod
    def normalize_result(self, result: Dict, file_data: Dict) -> Dict:
        """
        Normalize a tracker API result to a standard format.
        
        Args:
            result: Raw tracker API response
            file_data: Original file data
            
        Returns:
            Normalized result dictionary
        """
        pass

    def check_banned_groups(self, file_data: Dict, verbose: bool = False) -> bool:
        """
        Check if file's release group is banned on this tracker.
        
        Args:
            file_data: File data dictionary
            verbose: Whether to print verbose output
            
        Returns:
            True if group is banned, False otherwise
        """
        release_group = file_data.get("group", "")
        banned_groups = self.tracker_info.get("bannedGroups", [])

        if not release_group or not banned_groups:
            return False

        is_banned = release_group.lower() in [g.lower() for g in banned_groups]

        if is_banned and verbose:
            logger.warning(f"[{self.tracker}] Group {release_group} is banned on this tracker.")

        return is_banned

    def has_valid_api_key(self) -> bool:
        """Check if this tracker has a valid API key."""
        return bool(self.api_key)

    @staticmethod
    def check_resolution_match(file_resolution: str, tracker_resolution: str) -> bool:
        """
        Check if file resolution matches tracker resolution.
        
        Args:
            file_resolution: File's resolution string
            tracker_resolution: Tracker's resolution string
            
        Returns:
            True if resolutions match, False otherwise
        """
        if not file_resolution or not tracker_resolution:
            return False

        file_resolution = file_resolution.lower().replace(" ", "")
        tracker_resolution = tracker_resolution.lower().replace(" ", "")

        # Direct match
        if file_resolution == tracker_resolution:
            return True

        # Handle common variations
        if "2160" in file_resolution or "4k" in file_resolution:
            return "2160" in tracker_resolution or "4k" in tracker_resolution
        elif "1080" in file_resolution:
            return "1080" in tracker_resolution
        elif "720" in file_resolution:
            return "720" in tracker_resolution
        elif "480" in file_resolution:
            return "480" in tracker_resolution

        return False

    @staticmethod
    def check_quality_match(file_quality: str, tracker_quality: str) -> bool:
        """
        Check if file quality matches tracker quality.
        
        Args:
            file_quality: File's quality string
            tracker_quality: Tracker's quality string
            
        Returns:
            True if qualities match, False otherwise
        """
        if not file_quality or not tracker_quality:
            return False

        file_quality = file_quality.lower()
        tracker_quality = tracker_quality.lower()

        # Direct match
        if file_quality == tracker_quality:
            return True

        # Handle common variations
        remux_variants = ["remux", "bdremux", "uhd.remux"]
        bluray_variants = ["bluray", "blu-ray", "bd", "bdrip"]
        web_variants = ["web", "web-dl", "webdl", "webrip"]
        hdtv_variants = ["hdtv", "hdtvrip"]

        if any(variant in file_quality for variant in remux_variants):
            return any(variant in tracker_quality for variant in remux_variants)
        elif any(variant in file_quality for variant in bluray_variants):
            return any(variant in tracker_quality for variant in bluray_variants)
        elif any(variant in file_quality for variant in web_variants):
            return any(variant in tracker_quality for variant in web_variants)
        elif any(variant in file_quality for variant in hdtv_variants):
            return any(variant in tracker_quality for variant in hdtv_variants)

        return False

    def _check_hdr_slot_upgrade(self, file_tuple: tuple, existing_tuples: tuple):
        """
        Check if file is an upgrade based on HDR slot rules.
        
        Args:
            file_tuple: (quality, resolution, hdr_format) tuple for new file
            existing_tuples: List of tuples for existing files
            
        Returns:
            tuple: (is_upgrade, reason_message)
        """
        # Default to no upgrade if data is missing
        if not file_tuple or not existing_tuples:
            return False, "Missing data for HDR slot comparison"

        # Make sure we have all three pieces of info (quality, resolution, hdr_format)
        if len(file_tuple) < 3:
            return False, "Missing HDR format information"

        file_quality, file_resolution, file_hdr = file_tuple

        # ONLY use this for 4K content
        is_4k = "2160" in file_resolution or "4k" in file_resolution.lower()
        if not is_4k:
            return False, "Not 4K content"
        
        # Now we proceed with slot checking for 4K content
        return self.slot_checker.is_hdr_slot_upgrade(file_tuple, existing_tuples)
        

    def create_empty_result(self) -> Dict:
        """
        Create a simplified result structure focusing only on essential information.
        The main purpose is to determine if a file is safe to upload.
        """
        return {
            "exists_on_tracker": False,   # Does the file exist on tracker?
            "is_duplicate": False,        # Is it an exact duplicate?
            "duplicate_reason": "",       # Why it's considered a duplicate
            "is_upgrade": False,          # Is it an upgrade over existing files?
            "upgrade_reason": "",         # Why it's considered an upgrade
            "is_safe": False,             # Ultimate decision: safe to upload?
            "unsafe_reason": "",          # Why it's not safe (if applicable)
            "errors": [],                 # Any errors encountered
            "banned_group": False,        # Is the release group banned?
            "no_api_key": not self.has_valid_api_key()  # Missing API key?
        }

    def _is_hq_webrip(self, quality: str, group: str) -> bool:
        """
        Check if a release is a high-quality webrip from a known good group.
        
        Args:
            quality: Quality string
            group: Release group
            
        Returns:
            True if it's an HQ webrip, False otherwise
        """
        if not quality or not group:
            return False

        if quality.lower() != "webrip":
            return False

        return any(hq_group.lower() in group.lower() 
                  for hq_group in self.hq_webrip_groups)

    def _is_quality_resolution_upgrade(self, file_tuple, existing_tuples, file_data: Dict) -> bool:
        """
        Check if file is an upgrade over existing qualities based on quality/resolution.
        
        Args:
            file_tuple: (quality, resolution, hdr_format) tuple for the file
            existing_tuples: List of (quality, resolution, hdr_format) tuples for existing files
            file_data: Original file data
            
        Returns:
            True if file is an upgrade, False otherwise
        """
        if not file_tuple or not existing_tuples:
            # If no existing files, it's not an upgrade (just a new file)
            return False

        # Extract quality and resolution from tuples
        file_quality, file_resolution = file_tuple[0], file_tuple[1]
        file_group = file_data.get("group", "").lower()

        # Define quality hierarchy (where higher number = better quality)
        quality_hierarchy = self.settings.quality_hierarchy.copy()

        # Special handling for HQ webrips - our file is an HQ webrip
        if file_quality == "webrip" and self._is_hq_webrip(file_quality, file_group):
            quality_hierarchy["webrip"] = 3  # Above encode (2), below fulldisc (4)

        # Define resolution hierarchy (where higher number = better resolution)
        res_values = {
            "2160p": 10, "4k": 10, 
            "1080p": 8, "1080i": 7,
            "720p": 6, "720i": 5,
            "576p": 4, "480p": 3,
            "360p": 2, "240p": 1
        }

        file_quality_level = quality_hierarchy.get(file_quality, 0)
        file_res_level = res_values.get(file_resolution.lower(), 0)

        # Check against existing releases
        for existing_tuple in existing_tuples:
            # Extract quality and resolution
            existing_quality, existing_resolution = existing_tuple[0], existing_tuple[1]
            
            # Skip exact match
            if file_quality == existing_quality and file_resolution == existing_resolution:
                continue
                
            existing_quality_level = quality_hierarchy.get(existing_quality, 0)
            existing_res_level = res_values.get(existing_resolution.lower(), 0)

            # Special handling for existing HQ webrips
            if existing_quality == "webrip":
                hq_webrip_tuples = file_data.get("hq_webrip_tuples", [])
                if hq_webrip_tuples and any(
                    existing_quality == t[0] and existing_resolution == t[1] for t in hq_webrip_tuples
                ):
                    existing_quality_level = 3  # Same boost as our own HQ webrips

            # If our quality is worse than existing, not an upgrade
            if file_quality_level < existing_quality_level:
                return False

            # If same quality but worse or equal resolution, not an upgrade
            if file_quality_level == existing_quality_level and file_res_level <= existing_res_level:
                return False

        # If we've made it here, our file provides something new and better
        return True
        
    def _check_if_upgrade(self, file_quality: str, file_resolution: str, 
                         file_hdr_format: str, existing_tuples: list, 
                         file_data: Dict, verbose: bool = False) -> Tuple[bool, str]:
        """
        Common implementation for checking if a file is an upgrade.
        
        Args:
            file_quality: Quality string
            file_resolution: Resolution string
            file_hdr_format: HDR format string
            existing_tuples: List of (quality, resolution, hdr_format, group) tuples
            file_data: Original file data
            verbose: Whether to print verbose output
            
        Returns:
            Tuple of (is_upgrade, reason_message)
        """
        # Create file quality tuple
        file_tuple = (file_quality, file_resolution, file_hdr_format)

        # Extract just the quality tuples without group info
        quality_tuples = [(q, r, h) for q, r, h, _ in existing_tuples]

        # Identify HQ webrips for quality comparison
        hq_webrip_tuples = []
        for quality, resolution, hdr_format, group in existing_tuples:
            if quality == "webrip" and self._is_hq_webrip(quality, group):
                hq_webrip_tuples.append((quality, resolution, hdr_format))
                if verbose:
                    logger.debug(f"Found HQ webrip: {quality} {resolution} {group}")

        # First check HDR slot upgrade for 4K content ONLY
        if "2160" in file_resolution.lower() or "4k" in file_resolution.lower():
            is_hdr_upgrade, hdr_reason = self._check_hdr_slot_upgrade(
                file_tuple, quality_tuples
            )
            # Important: Return the result of the HDR slot check for 4K content
            return is_hdr_upgrade, hdr_reason

        # Then check quality/resolution upgrade for non-4K content
        extended_data = file_data.copy()
        extended_data["hq_webrip_tuples"] = hq_webrip_tuples

        is_quality_upgrade = self._is_quality_resolution_upgrade(
            file_tuple, quality_tuples, extended_data
        )

        if is_quality_upgrade:
            return True, "Quality/resolution upgrade over existing files"

        return False, "Not an upgrade over existing files"
        
    def _extract_file_info(self, file_data: Dict) -> Optional[Tuple[str, str, str]]:
        """Extract and validate basic file info needed for comparison."""
        file_quality = file_data.get("quality", "").lower()
        file_resolution = file_data.get("resolution", "").lower()
        file_media_info = file_data.get("media_info", {})

        # Get HDR format from media info
        file_hdr_format = file_media_info.get("hdr_format", "SDR")

        # Check if quality or resolution is missing
        if not file_quality or not file_resolution:
            return None

        return file_quality, file_resolution, file_hdr_format
        
    def _extract_existing_tuples(self, results: List[Dict], file_data: Dict, verbose: bool = False) -> List[Tuple]:
        """
        Extract information about existing files on the tracker.
        
        Args:
            results: List of search results from the tracker
            file_data: Original file data
            verbose: Whether to print verbose output
            
        Returns:
            List of (quality, resolution, hdr_format, group) tuples
        """
        # This method should be implemented by subclasses
        raise NotImplementedError("Subclasses must implement _extract_existing_tuples")

    def _should_search_tracker(self, file_data: Dict, verbose: bool = False):
        if not self.has_valid_api_key():
            empty_result = self.create_empty_result()
            empty_result["no_api_key"] = True
            empty_result["errors"].append(f"No API key for {self.tracker}")
            return empty_result

        # Check banned groups before making API call
        if self.check_banned_groups(file_data, verbose):
            result = self.create_empty_result()
            result["banned_group"] = True
            return result
        return True

    def _process_results(self, results: List[Dict], file_data: Dict, verbose: bool = False) -> Dict:
        """
        Process search results and determine if file exists on tracker and if it's an upgrade.
        
        Args:
            results: List of search results
            file_data: Original file data
            verbose: Whether to print verbose output
            
        Returns:
            Dict with structured search result
        """
        result_data = self.create_empty_result()

        # Get file metadata
        file_info = self._extract_file_info(file_data)
        if not file_info:
            if verbose:
                logger.warning(f"DANGER: Quality or resolution missing for {file_data.get('title')}")
            return result_data

        file_quality, file_resolution, file_hdr_format = file_info

        # Process tracker results - get existing files
        existing_tuples = self._extract_existing_tuples(results, file_data, verbose)
        
        # Set basic result data
        result_data["exists_on_tracker"] = len(existing_tuples) > 0

        # If nothing exists on tracker, it's automatically safe
        if not result_data["exists_on_tracker"]:
            result_data["is_safe"] = True
            return result_data

        # If exact duplicate found, it's not safe to upload
        if result_data.get("is_duplicate", False):
            result_data["is_safe"] = False
            return result_data

        # Check if file is an upgrade - by quality/resolution or HDR slot
        is_upgrade, upgrade_reason = self._check_if_upgrade(
            file_quality,
            file_resolution,
            file_hdr_format,
            existing_tuples,
            file_data,
            verbose,
        )

        if is_upgrade:
            result_data["is_upgrade"] = True
            result_data["upgrade_reason"] = upgrade_reason
            result_data["is_safe"] = True
        else:
            result_data["is_safe"] = False
            # Mark files that aren't upgrades as duplicates
            result_data["is_duplicate"] = True
            result_data["duplicate_reason"] = "Not an upgrade over existing files"
            result_data["unsafe_reason"] = "Not an upgrade over existing files"

        return result_data

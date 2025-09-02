#!/usr/bin/env python3
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Any


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

    @abstractmethod
    def search_by_tmdb(self, file_data: Dict, verbose: bool = False) -> Dict:
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
            print(f"[{self.tracker}] Group {release_group} is banned on this tracker.")
            
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
    
    def create_empty_result(self) -> Dict:
        """Create an empty result structure."""
        return {
            "exists_on_tracker": False,
            "is_exact_duplicate": False,
            "existing_qualities": [],
            "existing_quality_tuples": [],
            "hq_webrip_tuples": [],  # New field to track HQ webrips
            "file_quality_tuple": None,
            "is_upgrade": False,
            "errors": [],
            "banned_group": False,
            "missing_quality_info": False,  # New field to track missing quality/resolution
            "no_api_key": not self.has_valid_api_key(),
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
        Check if file is an upgrade over existing qualities.
        
        Args:
            file_tuple: (quality, resolution) tuple for the file
            existing_tuples: List of (quality, resolution) tuples for existing files
            file_data: Original file data
            
        Returns:
            True if file is an upgrade, False otherwise
        """
        # If the exact quality/resolution tuple already exists, it's not an upgrade
        if file_tuple in existing_tuples:
            return False
        
        file_quality, file_resolution = file_tuple
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
        for existing_quality, existing_resolution in existing_tuples:
            existing_tuple = (existing_quality, existing_resolution)
            existing_quality_level = quality_hierarchy.get(existing_quality, 0)
            existing_res_level = res_values.get(existing_resolution.lower(), 0)
            
            # Special handling for existing HQ webrips - check if it's in our hq_webrip_tuples list
            if existing_quality == "webrip":
                hq_webrip_tuples = file_data.get("hq_webrip_tuples", [])
                if existing_tuple in hq_webrip_tuples:
                    existing_quality_level = 3  # Same boost as our own HQ webrips
            
            # If our quality is worse than existing, not an upgrade
            if file_quality_level < existing_quality_level:
                return False
            
            # If same quality but worse or equal resolution, not an upgrade
            if file_quality_level == existing_quality_level and file_res_level <= existing_res_level:
                return False
        
        # If we've made it here, our file provides something new and better
        return True

#!/usr/bin/env python3
import re
import time
import requests
from typing import Dict, List, Optional, Tuple, Any
from .base import BaseTracker


class UNIT3DTracker(BaseTracker):
    """Implementation for trackers running the UNIT3D software."""

    def search_by_tmdb(self, file_data: Dict, verbose: bool = False) -> Dict:
        """
        Search the tracker for a file using TMDB ID.

        Args:
            file_data: File data dictionary with title, TMDB ID, etc.
            verbose: Whether to print verbose output

        Returns:
            Dict with structured search result
        """
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

        try:
            query_params = self.build_query(file_data)

            # Make request to the API
            url = f"{self.tracker_info.get('url')}api/torrents/filter"
            headers = {"Authorization": f"Bearer {self.api_key}"}

            if verbose:
                print(f"[{self.tracker}] Requesting: {url} with params: {query_params}")

            response = requests.get(
                url, headers=headers, params=query_params, timeout=30
            )
            response.raise_for_status()

            # Parse response
            data = response.json()

            if verbose:
                print(
                    f"[{self.tracker}] Response received: {len(data.get('data', []))} results"
                )

            # Process results
            results = data.get("data", [])

            # Handle pagination if available
            if "next" in data.get("links", {}):
                pass  # You could implement pagination handling here

            return self._process_results(results, file_data, verbose)

        except Exception as e:
            if verbose:
                print(f"[{self.tracker}] Error searching: {str(e)}")

            error_result = self.create_empty_result()
            error_result["errors"].append(f"Error searching {self.tracker}: {str(e)}")
            return error_result

    def build_query(self, file_data: Dict) -> Dict:
        """
        Build the query parameters for the UNIT3D API based on file data.

        Args:
            file_data: File data dictionary

        Returns:
            Dict with query parameters
        """
        # Prefer IMDB ID over TMDB ID
        imdb_id = file_data.get("imdb")
        tmdb_id = file_data.get("tmdb")
        
        # Common movie categories
        categories = {"categories[]": [1, 2, 3, 4, 5]}
        
        # If we have an IMDB ID, use it (UNIT3D expects IMDB ID without the 'tt' prefix)
        if imdb_id and imdb_id.startswith("tt"):
            imdb_id_without_tt = imdb_id.replace("tt", "")
            return {
                "imdbId": imdb_id_without_tt,
                **categories
            }
            
        # If no IMDB ID but we have TMDB ID, use that
        elif tmdb_id:
            return {
                "tmdbId": tmdb_id,
                **categories
            }
            
        # Fall back to title search if no IDs available
        return {"name": file_data.get("title", ""), **categories}

    def normalize_result(self, result: Dict, file_data: Dict) -> Tuple[str, str, str]:
        """
        Extract quality, resolution, and group from a UNIT3D result.

        Args:
            result: UNIT3D API result item
            file_data: Original file data

        Returns:
            Tuple of (quality, resolution, group)
        """
        attributes = result.get("attributes", {})

        # Try to parse from name
        name = attributes.get("name", "")

        # Extract quality, resolution from attributes
        quality = attributes.get("type", "")
        resolution = attributes.get("resolution", "")

        quality = quality.lower() if quality else ""
        resolution = resolution.lower() if resolution else ""
        
        # Extract group only if we need it for HQ_WEBRIP detection
        group = ""
        if "web" in quality and "rip" in quality:
            # Only extract group for webrips for HQ detection
            groupregex = r"(?<=-)[^-]*$"
            group_match = re.search(groupregex, name)
            if group_match:
                group = group_match.group(0).lower().strip()
            
        # Normalize quality to standard names
        if "remux" in quality:
            quality = "remux"
        elif "web" in quality and "dl" in quality:
            quality = "webdl"
        elif "web" in quality and "rip" in quality:
            quality = "webrip"
        elif "encode" in quality or "x264" in quality or "x265" in quality:
            quality = "encode"
        elif "full" in quality or "disc" in quality:
            quality = "fulldisc"
            
        return quality, resolution, group

    def _process_results(
        self, results: List[Dict], file_data: Dict, verbose: bool
    ) -> Dict:
        """
        Process search results and determine if file exists on tracker.

        Args:
            results: List of search results
            file_data: Original file data
            verbose: Whether to print verbose output

        Returns:
            Dict with structured search result
        """
        result_data = self.create_empty_result()

        # Extract file quality and resolution
        file_quality = file_data.get("quality", "").lower()
        file_resolution = file_data.get("resolution", "").lower()
        
        # Check if quality or resolution is missing - mark as dangerous
        if not file_quality or not file_resolution:
            result_data["missing_quality_info"] = True
            if verbose:
                print(f"DANGER: Quality or resolution missing for {file_data.get('title')}")
            return result_data

        file_quality_tuple = (file_quality, file_resolution)
        result_data["file_quality_tuple"] = file_quality_tuple

        existing_qualities = []
        existing_quality_tuples = []
        hq_webrip_tuples = []  # Track which tuples are HQ webrips

        # Check each result
        for result in results:
            quality, resolution, group = self.normalize_result(result, file_data)

            if quality and resolution:
                existing_tuple = (quality.lower(), resolution.lower())

                # Add to existing qualities if not already there
                if existing_tuple not in existing_quality_tuples:
                    existing_qualities.append(f"{quality} {resolution}")
                    existing_quality_tuples.append(existing_tuple)
                    
                    # Directly check if this is an HQ webrip and track it
                    if quality.lower() == "webrip" and self._is_hq_webrip(quality, group):
                        hq_webrip_tuples.append(existing_tuple)
                        if verbose:
                            print(f"Found HQ webrip: {quality} {resolution} from {group}")

                # Check for exact quality/resolution match
                if (
                    self.check_quality_match(file_quality, quality)
                    and self.check_resolution_match(file_resolution, resolution)
                ):
                    result_data["is_exact_duplicate"] = True

        # Set result data
        result_data["exists_on_tracker"] = len(existing_quality_tuples) > 0
        result_data["existing_qualities"] = existing_qualities
        result_data["existing_quality_tuples"] = existing_quality_tuples
        result_data["hq_webrip_tuples"] = hq_webrip_tuples  # Add this for use in upgrade check

        # Check if file is an upgrade
        if result_data["exists_on_tracker"]:
            # We'll extend file_data with our HQ webrip info for the upgrade check
            extended_data = file_data.copy()
            extended_data["hq_webrip_tuples"] = hq_webrip_tuples
            
            result_data["is_upgrade"] = self._is_quality_resolution_upgrade(
                file_quality_tuple, existing_quality_tuples, extended_data
            )

        return result_data

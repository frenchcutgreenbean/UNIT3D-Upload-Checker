#!/usr/bin/env python3
import time
import requests
from typing import Dict, List, Optional, Tuple, Any
from .base import BaseTracker
import re


class FenixTracker(BaseTracker):
    """Implementation for trackers running the F3NIX software."""

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
            url = f"{self.tracker_info.get('url')}api/torrents/{self.api_key}"
            if verbose:
                print_url = url.replace(self.api_key, "REDACTED")
                print(f"[{self.tracker}] Requesting: {print_url} with params: {query_params}")

            response = requests.post(url, params=query_params, timeout=30)
            response.raise_for_status()

            # Parse response
            data = response.json()

            # F3NIX returns results directly in 'results' key
            results = data.get("results", [])

            # Handle pagination if needed
            total_pages = data.get("total_pages", 1)
            current_page = data.get("page", 1)

            if verbose:
                print(
                    f"[{self.tracker}] Response received: {len(results)} results, page {current_page}/{total_pages}"
                )

            # Fetch additional pages if needed
            all_results = results
            if total_pages > 1:
                for page in range(2, total_pages + 1):
                    if verbose:
                        print(f"[{self.tracker}] Fetching page {page}/{total_pages}")

                    page_params = query_params.copy()
                    page_params["page"] = page

                    page_response = requests.post(url, params=page_params, timeout=30)
                    page_response.raise_for_status()

                    page_data = page_response.json()
                    all_results.extend(page_data.get("results", []))

                    # Respect rate limits
                    time.sleep(1)

            return self._process_results(all_results, file_data, verbose)

        except Exception as e:
            if verbose:
                print(f"[{self.tracker}] Error searching: {str(e)}")

            error_result = self.create_empty_result()
            error_result["errors"].append(f"Error searching {self.tracker}: {str(e)}")
            return error_result

    def build_query(self, file_data: Dict) -> Dict:
        """
        Build the query parameters for the F3NIX API based on file data.

        Args:
            file_data: File data dictionary

        Returns:
            Dict with query parameters
        """
        # Prefer IMDB ID over TMDB ID
        imdb_id = file_data.get("imdb")
        tmdb_id = file_data.get("tmdb")
        
        # If we have an IMDB ID, use it (F3NIX expects the full IMDB ID with 'tt' prefix)
        if imdb_id:
            return {
                "action": "search",
                "imdb_id": imdb_id,
            }
            
        # If no IMDB ID but we have TMDB ID, use that
        elif tmdb_id:
            return {
                "action": "search",
                "tmdb_id": f"movie/{tmdb_id}",
            }
            
        # Fall back to title search if no IDs available
        return {"search": file_data.get("title", "")}

    def normalize_result(self, result: Dict, file_data: Dict) -> Tuple[str, str, str]:
        """
        Extract quality, resolution, and group from a F3NIX result.

        Args:
            result: F3NIX API result item
            file_data: Original file data

        Returns:
            Tuple of (quality, resolution, group)
        """
        # F3NIX doesn't have 'attributes' key, fields are directly in the result
        name = result.get("name", "")
        torrent_type = result.get("type", "")  # Type field from F3NIX API

        # Use our parser to extract information
        torrent_info = self._parse_info_from_title(name, torrent_type)

        quality = torrent_info.get("quality", "")
        resolution = torrent_info.get("resolution", "")
        group = ""

        # Extract group only if we need it for HQ_WEBRIP detection
        if quality.lower() == "webrip":
            # Only extract group for webrips for HQ detection
            groupregex = r"(?<=-)[^-]*$"
            group_match = re.search(groupregex, name)
            if group_match:
                group = group_match.group(0)
            
        # Normalize quality to standard names
        quality = quality.lower()
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

    def _parse_info_from_title(self, torrent_title: str, torrent_type: str) -> Dict[str, str]:
        """
        Parse information from the torrent title.

        Args:
            torrent_title: The title of the torrent
            type: The type of the torrent (e.g., "BD 50", "1080p")

        Returns:
            A dictionary with parsed information
        """
        torrent_info = {
            "resolution": "",
            "quality": "",
            "group": ""
        }

        title_lower = torrent_title.lower()
        torrent_type = torrent_type.lower() if torrent_type else ""

        # We don't need to extract group in this method, as it's handled in normalize_result
        # when needed for HQ webrips

        # --- Resolution Extraction ---
        # First check for resolution in type
        resolution_mapping = {
            "2160p": "2160p",
            "1080p": "1080p",
            "1080i": "1080i",
            "720p": "720p",
            "576p": "576p",
            "540p": "540p",
            "480p": "480p"
        }

        if torrent_type in resolution_mapping:
            torrent_info["resolution"] = resolution_mapping[torrent_type]
        # Check for resolution in UHD types
        elif "uhd" in torrent_type:
            torrent_info["resolution"] = "2160p"
        # Check for BD and DVD types (non-remux)
        elif "bd" in torrent_type and "remux" not in torrent_type:
            # Try to find resolution in title
            if "2160" in title_lower or "4k" in title_lower:
                torrent_info["resolution"] = "2160p"
            else:
                torrent_info["resolution"] = "1080p"  # Default assumption for BD
        elif "dvd" in torrent_type and "remux" not in torrent_type:
            torrent_info["resolution"] = "480p"  # Default for DVD

        # If still no resolution, try to extract it from title
        if not torrent_info["resolution"]:
            for res in ["2160p", "4k", "1080p", "1080i", "720p", "576p", "540p", "480p"]:
                if res in title_lower:
                    torrent_info["resolution"] = "2160p" if res == "4k" else res
                    break

        # --- Quality Extraction ---
        # Handle Remuxes
        if "remux" in torrent_type:
            torrent_info["quality"] = "remux"
        # Handle Full Discs
        elif any(x in torrent_type for x in ["uhd 100", "uhd 66", "uhd 50", "bd 50", "bd 25", "dvd 9", "dvd 5"]):
            torrent_info["quality"] = "fulldisc"
        # Handle Web qualities - check title since type might just be resolution
        elif "web-dl" in title_lower or "webdl" in title_lower:
            torrent_info["quality"] = "webdl"
        elif "webrip" in title_lower:
            torrent_info["quality"] = "webrip"
        elif "web" in title_lower:
            torrent_info["quality"] = "web"
        # Any resolution type without special qualities is an encode
        elif torrent_type in resolution_mapping and not torrent_info["quality"]:
            torrent_info["quality"] = "encode"
        # Fallback
        else:
            # If it's one of the BD/DVD types but not a remux, it's a disc
            if any(x in torrent_type for x in ["bd", "uhd", "dvd"]) and "remux" not in torrent_type:
                torrent_info["quality"] = "fulldisc"
            else:
                torrent_info["quality"] = "encode"  # Default fallback

        return torrent_info

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

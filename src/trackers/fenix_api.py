#!/usr/bin/env python3
import re
import time
import traceback
from typing import Dict, List, Optional, Tuple

import requests

from src.utils import hdr_formats
from src.utils.logger import logger
from .base import BaseTracker


class FenixTracker(BaseTracker):
    """Implementation for trackers running the F3NIX software."""

    def search_tracker(self, file_data: Dict, verbose: bool = False) -> Dict:
        """
        Search the tracker for a file using TMDB ID.

        Args:
            file_data: File data dictionary with title, TMDB ID, etc.
            verbose: Whether to print verbose output

        Returns:
            Dict with structured search result
        """
        should_search = self._should_search_tracker(file_data, verbose)

        if not isinstance(should_search, bool):
            return should_search

        try:
            query_params = self.build_query(file_data)

            # Make request to the API
            url = f"{self.tracker_info.get('url')}api/torrents/{self.api_key}"
            if verbose:
                print_url = url.replace(self.api_key, "REDACTED")
                logger.debug(
                    f"[{self.tracker}] Requesting: {print_url} with params: {query_params}"
                )

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
                logger.debug(
                    f"[{self.tracker}] Response received: {len(results)} results, page {current_page}/{total_pages}"
                )

            # Fetch additional pages if needed
            all_results = results
            if total_pages > 1:
                for page in range(2, total_pages + 1):
                    if verbose:
                        logger.debug(f"[{self.tracker}] Fetching page {page}/{total_pages}")

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
                logger.error(f"[{self.tracker}] Error searching: {str(e)}")
                logger.debug(traceback.format_exc())

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

        # If no IMDB ID, but we have TMDB ID, use that
        elif tmdb_id:
            return {
                "action": "search",
                "tmdb_id": f"movie/{tmdb_id}",
            }

        # Fall back to title search if no IDs available
        return {"search": file_data.get("title", "")}

    def normalize_result(
        self, result: Dict, file_data: Dict
    ) -> Tuple[str, str, str, str]:
        """
        Extract quality, resolution, HDR format, and group from a F3NIX result.

        Args:
            result: F3NIX API result item
            file_data: Original file data

        Returns:
            Tuple of (quality, resolution, hdr_format, group)
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

        # Extract HDR format information
        hdr_format = self._extract_hdr_format(result)

        return quality, resolution, hdr_format, group

    @staticmethod
    def _extract_hdr_format(result: Dict) -> str:
        """
        Extract HDR format information from a F3NIX result.
        F3NIX provides direct HDR flags in the result (dv, hdr10, hdr10+).

        Args:
            result: F3NIX API result item

        Returns:
            String representing the HDR format using standardized format names
        """
        format_list = []

        # Check for Dolby Vision
        has_dv = result.get("dv", 0) == 1
        if has_dv:
            format_list.append(hdr_formats.DOLBY_VISION)

        # Check for HDR10+
        has_hdr10_plus = result.get("hdr10+", 0) == 1
        if has_hdr10_plus:
            format_list.append(hdr_formats.HDR10_PLUS)

        # Check for HDR (including HDR10)
        has_hdr = result.get("hdr10", 0) == 1 or result.get("hdr", 0) == 1
        if has_hdr and not has_hdr10_plus:
            format_list.append(hdr_formats.HDR)

        # Check for combined formats
        if has_dv and has_hdr10_plus:
            format_list.remove(hdr_formats.DOLBY_VISION)  # Replace with combined format
            # Remove HDR10+ to prevent duplication
            if hdr_formats.HDR10_PLUS in format_list:
                format_list.remove(hdr_formats.HDR10_PLUS)
            # Remove regular HDR if present
            if hdr_formats.HDR in format_list:
                format_list.remove(hdr_formats.HDR)
            format_list.append(hdr_formats.DOLBY_VISION_HDR10P)
        elif has_dv and has_hdr:
            format_list.remove(hdr_formats.DOLBY_VISION)  # Replace with combined format
            # Remove regular HDR to prevent duplication
            if hdr_formats.HDR in format_list:
                format_list.remove(hdr_formats.HDR)
            format_list.append(hdr_formats.DOLBY_VISION_HDR)

        # If no HDR formats detected, it's SDR
        if not format_list:
            return hdr_formats.SDR

        return ", ".join(sorted(format_list))

    @staticmethod
    def _parse_info_from_title(
            torrent_title: str, torrent_type: str
    ) -> Dict[str, str]:
        """
        Parse information from the torrent title.

        Args:
            torrent_title: The title of the torrent
            torrent_type: The type of the torrent (e.g., "BD 50", "1080p")

        Returns:
            A dictionary with parsed information
        """
        torrent_info = {"resolution": "", "quality": "", "group": ""}

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
            "480p": "480p",
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
            for res in [
                "2160p",
                "4k",
                "1080p",
                "1080i",
                "720p",
                "576p",
                "540p",
                "480p",
            ]:
                if res in title_lower:
                    torrent_info["resolution"] = "2160p" if res == "4k" else res
                    break

        # --- Quality Extraction ---
        # Handle Remuxes
        if "remux" in torrent_type:
            torrent_info["quality"] = "remux"
        # Handle Full Discs
        elif any(
            x in torrent_type
            for x in ["uhd 100", "uhd 66", "uhd 50", "bd 50", "bd 25", "dvd 9", "dvd 5"]
        ):
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
            if (
                any(x in torrent_type for x in ["bd", "uhd", "dvd"])
                and "remux" not in torrent_type
            ):
                torrent_info["quality"] = "fulldisc"
            else:
                torrent_info["quality"] = "encode"  # Default fallback

        return torrent_info

    def _process_results(
        self, results: List[Dict], file_data: Dict, verbose: bool
    ) -> Dict:
        """
        Process search results and determine if file exists on tracker and if it's an upgrade.

        Simplifies the decision process to focus on:
        1. Does the file exist?
        2. Is it a duplicate?
        3. Is it an upgrade (by quality/resolution or HDR slot)?

        Args:
            results: List of search results
            file_data: Original file data
            verbose: Whether to print verbose output

        Returns:
            Dict with simplified search result focused on safety determination
        """
        result_data = self.create_empty_result()

        # Get file metadata
        file_info = self._extract_file_info(file_data)
        if not file_info:
            if verbose:
                print(
                    f"DANGER: Quality or resolution missing for {file_data.get('title')}"
                )
            return result_data

        file_quality, file_resolution, file_hdr_format = file_info

        # Process tracker results
        existing_tuples = []

        # Check each result
        for result in results:
            quality, resolution, hdr_format, group = self.normalize_result(
                result, file_data
            )

            # Skip results with missing data
            if not quality or not resolution:
                continue

            # Check for exact duplicate
            if (
                self.check_quality_match(file_quality, quality)
                and self.check_resolution_match(file_resolution, resolution)
                and file_hdr_format == hdr_format
            ):
                result_data["is_duplicate"] = True
                result_data["duplicate_reason"] = (
                    f"Exact duplicate exists: {quality} {resolution} {hdr_format}"
                )
                # We could return early here, but let's collect all data for reference

            # Add to existing qualities
            existing_tuple = (
                quality.lower(),
                resolution.lower(),
                hdr_format,
                group.lower(),
            )
            if existing_tuple not in existing_tuples:
                existing_tuples.append(existing_tuple)

        # Set basic result data
        result_data["exists_on_tracker"] = len(existing_tuples) > 0

        # If nothing exists on tracker, it's automatically safe
        if not result_data["exists_on_tracker"]:
            result_data["is_safe"] = True
            return result_data

        # If exact duplicate found, it's not safe to upload
        if result_data["is_duplicate"]:
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
        elif not is_upgrade and file_resolution == "2160p":
            result_data["is_duplicate"] = True
            result_data["duplicate_reason"] = "Not an upgrade over existing files"
        else:
            result_data["is_safe"] = False
            result_data["unsafe_reason"] = "Not an upgrade over existing files"

        return result_data

    def _extract_file_info(self, file_data: Dict) -> Optional[Tuple[str, str, str]]:
        """Extract and validate basic file info needed for comparison."""
        # Use the base implementation
        return super()._extract_file_info(file_data)

    def _check_if_upgrade(
        self,
        file_quality: str,
        file_resolution: str,
        file_hdr_format: str,
        existing_tuples: List[Tuple],
        file_data: Dict,
        verbose: bool = False,
    ) -> Tuple[bool, str]:
        """
        Unified method to check if file is an upgrade by either quality/resolution or HDR slot.

        Returns:
            Tuple of (is_upgrade, reason_message)
        """
        # Use the base implementation from BaseTracker
        return super()._check_if_upgrade(
            file_quality,
            file_resolution,
            file_hdr_format,
            existing_tuples,
            file_data,
            verbose,
        )

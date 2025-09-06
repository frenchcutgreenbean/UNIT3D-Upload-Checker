#!/usr/bin/env python3
import re
import traceback
from typing import Dict, List, Optional, Tuple

import requests

from src.utils import hdr_formats
from src.utils.logger import logger
from .base import BaseTracker


class UNIT3DTracker(BaseTracker):
    """Implementation for trackers running the UNIT3D software."""

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
            url = f"{self.tracker_info.get('url')}api/torrents/filter"
            headers = {"Authorization": f"Bearer {self.api_key}"}

            if verbose:
                logger.debug(f"[{self.tracker}] Requesting: {url} with params: {query_params}")

            response = requests.get(
                url, headers=headers, params=query_params, timeout=30
            )
            response.raise_for_status()

            # Parse response
            data = response.json()

            if verbose:
                logger.debug(
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
                logger.error(f"[{self.tracker}] Error searching: {str(e)}")
                logger.debug(traceback.format_exc())

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
            return {"imdbId": imdb_id_without_tt, **categories}

        # If no IMDB ID, but we have TMDB ID, use that
        elif tmdb_id:
            return {"tmdbId": tmdb_id, **categories}

        # Fall back to title search if no IDs available
        return {"name": file_data.get("title", ""), **categories}

    def normalize_result(self, result: Dict, file_data: Dict) -> tuple[str, str, str, str]:
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

        media_info = attributes.get("media_info", "")
        hdr_format = self._media_info_parser(media_info)

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
        elif "encode" in quality:
            quality = "encode"
        elif "full" in quality or "disc" in quality:
            quality = "fulldisc"

        return quality, resolution, hdr_format, group

    @staticmethod
    def _media_info_parser(media_info: str) -> str:
        """
        Parse media info string attribute for HDR information
        """
        hdr_fs = set()
        # Ensure media_info is a string to prevent NoneType error
        media_info = media_info or ""
        media_info_lower = media_info.lower()
        regexes = hdr_formats.HDR_REGEXES

        # Check for Dolby Vision
        has_dv = re.search(regexes[hdr_formats.DOLBY_VISION], media_info_lower)
        if has_dv:
            hdr_fs.add(hdr_formats.DOLBY_VISION)

        # Check for HDR10+
        has_hdr10_plus = re.search(regexes[hdr_formats.HDR10_PLUS], media_info_lower)
        if has_hdr10_plus:
            hdr_fs.add(hdr_formats.HDR10_PLUS)

        # Check for HDR (including HDR10)
        has_hdr = re.search(regexes[hdr_formats.HDR], media_info_lower)
        if has_hdr and not has_hdr10_plus:  # Only add HDR if no HDR10+
            hdr_fs.add(hdr_formats.HDR)

        # Check for combined formats - ensure we don't have duplicates
        if has_dv and has_hdr10_plus:
            hdr_fs.discard(hdr_formats.DOLBY_VISION)  # Replace with combined format
            hdr_fs.discard(hdr_formats.HDR)  # Remove regular HDR if present
            hdr_fs.add(hdr_formats.DOLBY_VISION_HDR10P)
        elif has_dv and has_hdr:
            hdr_fs.discard(hdr_formats.DOLBY_VISION)  # Replace with combined format
            hdr_fs.discard(hdr_formats.HDR)  # Remove regular HDR to prevent duplication
            hdr_fs.add(hdr_formats.DOLBY_VISION_HDR)

        # If no HDR detected, it's SDR
        if not hdr_fs:
            hdr_fs.add(hdr_formats.SDR)
        hdr_format = ", ".join(sorted(hdr_fs))

        return hdr_format

    @staticmethod
    def _check_exact_match(file_data: Dict, results: List[Dict]) -> bool:
        """
        Check if the file_data filename matches any filename in results.
        With UNIT3D apis each result has result["attributes"]["files"] -> list[dict] and each file dict has "name".
        """
        target = (file_data.get("file_name") or "").strip().lower()
        if not target:
            return False

        existing_names = {
            (f.get("name") or "").strip().lower()
            for res in results
            for f in res.get("attributes", {}).get("files", [])
            if isinstance(f, dict)
        }

        return target in existing_names

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
                logger.warning(
                    f"DANGER: Quality or resolution missing for {file_data.get('title')}"
                )
            return result_data

        file_quality, file_resolution, file_hdr_format = file_info

        # Process tracker results
        existing_tuples = []

        # Before continuing, check for exact matches
        if self._check_exact_match(file_data, results):
            result_data["is_duplicate"] = True
            result_data["duplicate_reason"] = "Exact match found in results"
            return result_data

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
            # Ensure all values are strings before calling .lower()
            quality_safe = quality.lower() if quality else ""
            resolution_safe = resolution.lower() if resolution else ""
            group_safe = group.lower() if group else ""
            existing_tuple = (quality_safe, resolution_safe, hdr_format, group_safe)
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
        else:
            result_data["is_safe"] = False
            result_data["is_duplicate"] = True
            result_data["duplicate_reason"] = "Not an upgrade over existing files"
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
            verbose
        )

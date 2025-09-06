#!/usr/bin/env python3
"""
File Screener - Early safety checks before API calls.
Identifies obviously problematic files to avoid wasting API calls.
Also handles media info extraction for files that pass basic screening.
"""
from typing import Dict, Tuple

from ..mediainfo import get_media_info
from ..utils.logger import get_logger

# Initialize logger
logger = get_logger()


class FileScreener:
    """
    Performs early screening of files to identify obvious issues before API calls.
    This helps avoid wasting API calls on files that would be classified as dangerous.
    """
    
    def __init__(self, settings_manager, tmdb_matcher=None):
        self.settings = settings_manager
        self.tmdb_matcher = tmdb_matcher

    def screen_file(self, file_data: Dict, verbose: bool = False) -> Tuple[bool, str, Dict]:
        """
        Screen a file for obvious issues before API calls and extract media info.
        
        Args:
            file_data: File data dictionary from file_scanner
            verbose: Whether to print verbose output
            
        Returns:
            Tuple of (is_safe_to_proceed, reason_if_not, updated_file_data)
        """
        # Extract media info if not already present
        if not file_data.get("media_info"):
            if verbose:
                logger.debug(f"  📄 Extracting media info for {file_data.get('title', file_data.get('file_name', ''))}...")
            
            # Get media info
            file_path = file_data.get("file_location", "")
            if not file_path:
                logger.error("Missing file location")
                return False, "Missing file location", file_data
                
            media_info = get_media_info(file_path)
            file_data["media_info"] = media_info
            file_data["has_english_content"] = media_info.get("has_english_content", False)
        
        media_info = file_data.get("media_info", {})
        
        # Basic checks before even attempting TMDB matching
        # 1. Check for missing quality/resolution info
        if not file_data.get("quality") or not file_data.get("resolution"):
            return False, "Missing quality or resolution information", file_data
        
        # Check for missing English content only if we have TMDB data (post-TMDB check)
        if file_data.get("tmdb") and not media_info.get("has_english_content", True):
            return False, "No English audio or subtitles found", file_data
            
        # Check for year mismatch + failed verification only if we have TMDB data
        if file_data.get("tmdb") and self._has_year_mismatch_danger(file_data, media_info):
            return False, "Year mismatch with failed verification checks", file_data
            
        # All checks passed, file is safe to proceed
        return True, "", file_data
        
    def _has_year_mismatch_danger(self, file_data: Dict, media_info: Dict) -> bool:
        """Check if year mismatch qualifies as danger (failed majority of safety checks)."""
        file_year = file_data.get("year", "")
        tmdb_year = file_data.get("tmdb_year", "")
        
        # No mismatch = no danger
        if not file_year or not tmdb_year or file_year == tmdb_year:
            return False
        
        # Run safety verification checks
        safety_score = self._run_year_mismatch_verification(file_data, media_info)
        
        # Danger if failed majority (less than 2 out of 3 checks)
        return safety_score < 2

    def _run_year_mismatch_verification(self, file_data: Dict, media_info: Dict) -> int:
        """Run verification checks for year mismatch. Returns score 0-3."""
        safety_score = 0
        
        file_year = file_data.get("year", "")
        tmdb_year = file_data.get("tmdb_year", "")
        tmdb_id = file_data.get("tmdb")
        
        # Check 1: Year difference within 1 year
        try:
            year_diff = abs(int(file_year) - int(tmdb_year))
            if year_diff <= 1:
                safety_score += 1
        except (ValueError, TypeError):
            pass
        
        # Check 2 & 3: Runtime and language verification via TMDB
        if tmdb_id and self.tmdb_matcher:
            tmdb_info = self.tmdb_matcher.get_tmdb_movie_details(tmdb_id)
            
            if tmdb_info:
                # Check 2: Runtime match
                if self._verify_runtime_match(media_info, tmdb_info):
                    safety_score += 1
                
                # Check 3: Language match
                if self._verify_language_match(media_info, tmdb_info):
                    safety_score += 1
        
        return safety_score

    def _verify_runtime_match(self, media_info: Dict, tmdb_info: Dict) -> bool:
        """Verify runtime matches between file and TMDB."""
        if not media_info or not tmdb_info:
            return False
            
        file_runtime = media_info.get("runtime")
        tmdb_runtime = tmdb_info.get("runtime")
        
        if file_runtime and tmdb_runtime and self.tmdb_matcher:
            return self.tmdb_matcher.is_runtime_match(file_runtime, tmdb_runtime)
        
        return False

    @staticmethod
    def _verify_language_match(media_info: Dict, tmdb_info: Dict) -> bool:
        """Verify language matches between file and TMDB."""
        if not media_info or not tmdb_info:
            return False
            
        tmdb_lang = tmdb_info.get("original_language", "")
        if not tmdb_lang:
            return False
        tmdb_lang = tmdb_lang.lower()
            
        audio_langs = media_info.get("audio_language(s)", [])
        if isinstance(audio_langs, str):
            audio_langs = [audio_langs]
        
        return any(lang and lang.lower().startswith(tmdb_lang) for lang in audio_langs if lang is not None)

#!/usr/bin/env python3
"""
Safety Classifier - Clean, simple categorization system.
Determines file safety based on clear criteria from README.
"""
from typing import Dict, List, Tuple, Optional


class SafetyClassifier:
    """Classifies files into safety categories based on clear rules."""
    
    def __init__(self, settings_manager, tmdb_matcher=None):
        self.settings = settings_manager
        self.tmdb_matcher = tmdb_matcher

    def classify_file(self, file_data: Dict, tracker_results: Dict, media_info: Dict) -> Dict:
        """
        Classify a file's safety across all trackers.
        Returns dict with tracker -> classification mapping.
        """
        classifications = {}
        
        for tracker, tracker_data in tracker_results.items():
            classification = self._classify_single_tracker(
                file_data, tracker, tracker_data, media_info
            )
            classifications[tracker] = classification
            
        return classifications

    def _classify_single_tracker(self, file_data: Dict, tracker: str, 
                               tracker_data: Dict, media_info: Dict) -> Dict:
        """Classify file safety for a single tracker."""
        
        # First check DANGER conditions (highest priority)
        danger_reasons = self._check_danger_conditions(file_data, tracker_data, media_info)
        if danger_reasons:
            return {
                "category": "danger",
                "reason": danger_reasons[0],  # Primary reason
                "details": danger_reasons
            }
        
        # Then check tracker-specific conditions (SAFE vs RISKY)
        tracker_classification = self._classify_tracker_result(file_data, tracker_data)
        
        return tracker_classification

    def _check_danger_conditions(self, file_data: Dict, tracker_data: Dict, 
                               media_info: Dict) -> List[str]:
        """Check for DANGER conditions. Returns list of reasons."""
        danger_reasons = []
        
        # 1. Year mismatch + failed safety checks
        if self._has_year_mismatch_danger(file_data, media_info):
            danger_reasons.append("Year mismatch with failed verification checks")
        
        # 2. No English audio or subtitles
        if self._has_no_english_content(media_info):
            danger_reasons.append("No English audio or subtitles found")
        
        # 3. Quality or resolution missing
        if self._has_missing_quality_info(tracker_data):
            danger_reasons.append("Quality or resolution could not be determined")
            
        return danger_reasons

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

    def _verify_language_match(self, media_info: Dict, tmdb_info: Dict) -> bool:
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

    def _has_no_english_content(self, media_info: Dict) -> bool:
        """Check if file has no English audio or subtitles."""
        if not media_info:
            return False
            
        audio_languages = media_info.get("audio_language(s)", [])
        subtitles = media_info.get("subtitle(s)", [])

        # Ensure they are lists
        if isinstance(audio_languages, str):
            audio_languages = [audio_languages]
        if isinstance(subtitles, str):
            subtitles = [subtitles]

        has_english_audio = any(
            lang and lang.lower().startswith("en") for lang in audio_languages if lang is not None
        )
        has_english_subs = any(
            sub and sub.lower().startswith("en") for sub in subtitles if sub is not None
        )

        return not has_english_audio and not has_english_subs

    def _has_missing_quality_info(self, tracker_data: Dict) -> bool:
        """Check if quality or resolution could not be determined from the file or tracker results."""
        return tracker_data.get("missing_quality_info", False) or tracker_data.get("quality_unknown_conflict", False)

    def _classify_tracker_result(self, file_data: Dict, tracker_data: Dict) -> Dict:
        """Classify based on tracker search results (SAFE vs RISKY)."""
        
        # File doesn't exist on tracker = SAFE
        if not tracker_data.get("exists_on_tracker", False):
            return {
                "category": "safe",
                "reason": "New release - not found on tracker",
                "details": []
            }
        
        # File exists - check if it's an upgrade or downgrade
        if tracker_data.get("is_upgrade", False):
            return {
                "category": "safe", 
                "reason": "Quality/resolution upgrade over existing releases",
                "details": [f"Upgrade from: {', '.join(tracker_data.get('existing_qualities', []))}"]
            }
        
        # File exists but not an upgrade = RISKY
        return {
            "category": "risky",
            "reason": "New quality/resolution but may be downgrade from existing",
            "details": [f"Existing qualities: {', '.join(tracker_data.get('existing_qualities', []))}"]
        }

#!/usr/bin/env python3
"""
Safety Classifier - Focused on tracker-specific safety checks.
Works with FileScreener which handles early general safety checks.
"""
from typing import Dict


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
        """
        Classify file safety for a single tracker.
        
        Note: Early screening of obvious issues should have already been performed
        by FileScreener. This method focuses on tracker-specific safety classification.
        """
            
        # Then check tracker-specific conditions (SAFE vs RISKY)
        tracker_classification = self._classify_tracker_result(file_data, tracker_data)
        
        return tracker_classification

    @staticmethod
    def _classify_tracker_result(file_data: Dict, tracker_data: Dict) -> Dict:
        """Classify based on tracker search results (SAFE vs RISKY)."""
        
        # File doesn't exist on tracker = SAFE
        if not tracker_data.get("exists_on_tracker", False):
            return {
                "category": "safe",
                "reason": "New release - not found on tracker",
                "details": []
            }
        
        # File exists - check if it's an upgrade
        if tracker_data.get("is_upgrade", False):
            return {
                "category": "safe", 
                "reason": tracker_data.get("upgrade_reason", "Quality/resolution upgrade"),
                "details": []
            }
        
        # File exists but not an upgrade = RISKY
        return {
            "category": "risky",
            "reason": tracker_data.get("unsafe_reason", "Not an upgrade over existing files"),
            "details": []
        }

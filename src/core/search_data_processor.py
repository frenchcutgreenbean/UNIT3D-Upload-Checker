#!/usr/bin/env python3
import traceback
from typing import Dict

from .safety_classifier import SafetyClassifier
from ..utils.logger import get_logger

# Initialize logger
logger = get_logger()


class SearchDataProcessor:
    """Processes search results and categorizes them by safety level using the new classification system."""
    
    def __init__(self, tmdb_matcher, settings_manager):
        self.tmdb_matcher = tmdb_matcher
        self.safety_classifier = SafetyClassifier(settings_manager, tmdb_matcher)

    def create_search_data(self, scan_data: Dict, enabled_sites: list, verbose: bool = False) -> Dict:
        """Create search data by processing scan results and categorizing by safety level."""
        try:
            logger.section("Creating Search Data")
            logger.info("Processing scan results and categorizing by safety level...")
            
            # Initialize search data structure
            search_data = {}
            for tracker in enabled_sites:
                search_data[tracker] = {
                    "safe": {},
                    "risky": {},
                }

            # Count total files for progress tracking
            total_files = sum(len(files) for files in scan_data.values())
            processed_count = 0
            
            # Track statistics
            stats = {
                "processed": 0,
                "skipped": 0,
                "safe": 0,
                "risky": 0, 
                "duplicates": 0
            }

            if verbose:
                logger.info(f"📊 Found {total_files} files across {len(scan_data)} directories")
                logger.info("🔍 Processing files and extracting media information...")

            # Process each file
            for directory in scan_data:
                if verbose:
                    logger.info(f"📁 Processing directory: {directory}")
                    
                for file_name, file_data in scan_data[directory].items():
                    processed_count += 1
                    
                    # Progress indicator (every 10 files or if verbose)
                    if verbose or processed_count % 10 == 0 or processed_count == total_files:
                        progress = (processed_count / total_files) * 100
                        logger.info(f"⏳ Progress: {processed_count}/{total_files} ({progress:.1f}%) - {file_name[:50]}...")
                    
                    # If file is banned, just skip it completely
                    if file_data.get("banned", False):
                        continue
                        
                    # Skip files with no tracker data
                    if "trackers" not in file_data:
                        stats["skipped"] += 1
                        continue

                    stats["processed"] += 1

                    # Media info should now already exist from file scanner
                    media_info = file_data.get("media_info", {})
                    if not media_info and verbose:
                        logger.warning(f"⚠️ Warning: No media info available")

                    # Process each tracker result using the new classifier
                    trackers_data = file_data.get("trackers", {})
                    
                    if verbose:
                        logger.debug(f"🔍 Classifying safety for {len(trackers_data)} trackers...")
                    
                    try:
                        classifications = self.safety_classifier.classify_file(
                            file_data, trackers_data, media_info
                        )

                        for tracker, classification in classifications.items():
                            try:
                                # Skip if tracker has banned_group flag set
                                if trackers_data.get(tracker, {}).get("banned_group", False):
                                    if verbose:
                                        logger.debug(f"{tracker}: Banned group - skipping")
                                    continue
                                
                                # Skip duplicates
                                if trackers_data.get(tracker, {}).get("is_duplicate"):
                                    stats["duplicates"] += 1
                                    if verbose:
                                        logger.debug(f"{tracker}: Duplicate - skipping")
                                    continue

                                # Build clean file info
                                file_info = self._build_clean_file_info(file_data, classification, media_info)
                                
                                # Add to appropriate category
                                category = classification["category"]
                                title = file_data["title"]
                                search_data[tracker][category][title] = file_info
                                
                                # Update stats
                                stats[category] += 1
                                
                                if verbose:
                                    emoji = {"safe": "🟢", "risky": "🟡"}[category]
                                    logger.debug(f"      {emoji} {tracker}: {category.upper()} - {classification['reason']}")

                            except Exception as e:
                                logger.error(f"❌ Error processing {tracker} for {file_data['title']}: {e}")
                                logger.debug(traceback.format_exc())

                    except Exception as e:
                        logger.error(f"❌ Error classifying {file_data['title']}: {e}")
                        logger.debug(traceback.format_exc())

            self._print_processing_summary(stats, verbose)
            return search_data

        except Exception as e:
            logger.error(f"❌ Error creating search_data.json: {e}")
            logger.debug(traceback.format_exc())
            return {}

    @staticmethod
    def _should_skip_file_for_search_data(file_data: Dict) -> bool:
        """Check if file should be skipped during search data creation."""
        # Skip files without tracker data
        if "trackers" not in file_data:
            return True
        return False

    @staticmethod
    def _build_clean_file_info(file_data: Dict, classification: Dict, media_info: Dict) -> Dict:
        """Build clean file info without confusing messages."""
        return {
            "file_location": file_data["file_location"],
            "year": file_data.get("year", ""),
            "quality": file_data.get("quality", ""),
            "resolution": file_data.get("resolution", ""),
            "tmdb": file_data.get("tmdb"),
            "tmdb_year": file_data.get("tmdb_year", ""),
            "file_size": file_data.get("file_size", ""),
            "media_info": media_info,
            "reason": classification["reason"],
            "details": classification.get("details", [])
        }

    @staticmethod
    def _print_processing_summary(stats: Dict, verbose: bool = False):
        """Print summary of processing results."""
        logger.section("Search Data Processing Summary")
        logger.info(f"✓ Files processed: {stats['processed']}")
        logger.info(f"→ Files skipped: {stats['skipped']}")
        logger.info(f"🟢 Safe uploads: {stats['safe']}")
        logger.info(f"🟡 Risky uploads: {stats['risky']}")
        logger.info(f"🚫 Duplicates: {stats['duplicates']}")

        total_categorized = stats['safe'] + stats['risky']
        if total_categorized > 0:
            safe_pct = (stats['safe'] / total_categorized) * 100
            risky_pct = (stats['risky'] / total_categorized) * 100
            
            if verbose:
                logger.section("Classification Breakdown")
                logger.info(f"🟢 Safe: {safe_pct:.1f}%")
                logger.info(f"🟡 Risky: {risky_pct:.1f}%")

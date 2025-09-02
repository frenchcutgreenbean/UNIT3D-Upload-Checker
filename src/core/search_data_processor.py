#!/usr/bin/env python3
from typing import Dict, Optional
from ..mediainfo import get_media_info
from .safety_classifier import SafetyClassifier


class SearchDataProcessor:
    """Processes search results and categorizes them by safety level using the new classification system."""
    
    def __init__(self, tmdb_matcher, settings_manager):
        self.tmdb_matcher = tmdb_matcher
        self.safety_classifier = SafetyClassifier(settings_manager, tmdb_matcher)

    def create_search_data(self, scan_data: Dict, enabled_sites: list, verbose: bool = False) -> Dict:
        """Create search data by processing scan results and categorizing by safety level."""
        try:
            print("Creating search data...")
            
            # Initialize search data structure
            search_data = {}
            for tracker in enabled_sites:
                search_data[tracker] = {
                    "safe": {},
                    "risky": {},
                    "danger": {},
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
                "danger": 0,
                "exact_dupes": 0,
                "media_info_extracted": 0
            }

            if verbose:
                print(f"📊 Found {total_files} files across {len(scan_data)} directories")
                print("🔍 Processing files and extracting media information...")
                print()

            # Process each file
            for directory in scan_data:
                if verbose:
                    print(f"📁 Processing directory: {directory}")
                    
                for file_name, file_data in scan_data[directory].items():
                    processed_count += 1
                    
                    # Progress indicator (every 10 files or if verbose)
                    if verbose or processed_count % 10 == 0 or processed_count == total_files:
                        progress = (processed_count / total_files) * 100
                        print(f"⏳ Progress: {processed_count}/{total_files} ({progress:.1f}%) - {file_name[:50]}...")
                    
                    if self._should_skip_file_for_search_data(file_data):
                        if verbose:
                            print(f"   ⏭️  Skipping: {file_data.get('title', file_name)} (banned or no tracker data)")
                        stats["skipped"] += 1
                        continue

                    stats["processed"] += 1

                    # Extract media info once if needed
                    if "media_info" not in file_data:
                        if verbose:
                            print(f"   🎬 Extracting media info...")
                        file_location = file_data["file_location"]
                        media_info = get_media_info(file_location)
                        scan_data[directory][file_name]["media_info"] = media_info
                        stats["media_info_extracted"] += 1
                    else:
                        media_info = file_data["media_info"]
                        if verbose:
                            print(f"   ✅ Media info already available")

                    # Process each tracker result using the new classifier
                    trackers_data = file_data.get("trackers", {})
                    
                    if verbose:
                        print(f"   🔍 Classifying safety for {len(trackers_data)} trackers...")
                    
                    try:
                        classifications = self.safety_classifier.classify_file(
                            file_data, trackers_data, media_info
                        )

                        for tracker, classification in classifications.items():
                            try:
                                # Skip exact duplicates
                                if trackers_data.get(tracker, {}).get("is_exact_duplicate"):
                                    stats["exact_dupes"] += 1
                                    if verbose:
                                        print(f"      🚫 {tracker}: Exact duplicate - skipping")
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
                                    emoji = {"safe": "🟢", "risky": "🟡", "danger": "🔴"}[category]
                                    print(f"      {emoji} {tracker}: {category.upper()} - {classification['reason']}")

                            except Exception as e:
                                print(f"      ❌ Error processing {tracker} for {file_data['title']}: {e}")

                    except Exception as e:
                        print(f"   ❌ Error classifying {file_data['title']}: {e}")

            self._print_processing_summary(stats, verbose)
            return search_data

        except Exception as e:
            print(f"❌ Error creating search_data.json: {e}")
            import traceback
            if verbose:
                traceback.print_exc()
            return {}

    def _should_skip_file_for_search_data(self, file_data: Dict) -> bool:
        """Check if file should be skipped during search data creation."""
        if file_data.get("banned", False):
            return True
        if "trackers" not in file_data:
            return True
        return False

    def _build_clean_file_info(self, file_data: Dict, classification: Dict, media_info: Dict) -> Dict:
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

    def _print_processing_summary(self, stats: Dict, verbose: bool = False):
        """Print summary of processing results."""
        print(f"\n📊 Search Data Processing Summary:")
        print(f"  ✓ Files processed: {stats['processed']}")
        
        if verbose:
            print(f"  📋 Media info extracted: {stats['media_info_extracted']}")
        
        print(f"  → Files skipped: {stats['skipped']}")
        print(f"  🟢 Safe uploads: {stats['safe']}")
        print(f"  🟡 Risky uploads: {stats['risky']}")
        print(f"  🔴 Dangerous uploads: {stats['danger']}")
        print(f"  🚫 Exact duplicates: {stats['exact_dupes']}")
        
        total_categorized = stats['safe'] + stats['risky'] + stats['danger']
        if total_categorized > 0:
            safe_pct = (stats['safe'] / total_categorized) * 100
            risky_pct = (stats['risky'] / total_categorized) * 100
            danger_pct = (stats['danger'] / total_categorized) * 100
            
            if verbose:
                print(f"\n📈 Classification Breakdown:")
                print(f"  🟢 Safe: {safe_pct:.1f}%")
                print(f"  🟡 Risky: {risky_pct:.1f}%")
                print(f"  🔴 Danger: {danger_pct:.1f}%")
        
        print()

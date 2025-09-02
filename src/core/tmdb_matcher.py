#!/usr/bin/env python3
import re
import json
import requests
from urllib.parse import quote
from thefuzz import fuzz
from typing import Dict, Optional

# Constants
MIN_VOTE_COUNT = 5  # Minimum vote count on TMDB to consider as a match
FUZZY_MATCH_THRESHOLD = 75  # Minimum fuzzy match score to consider as a match


class TMDBMatcher:
    """Handles TMDB searches and movie matching."""

    def __init__(self, tmdb_api_key: str):
        self.tmdb_api_key = tmdb_api_key

    def search_tmdb_for_files(self, scan_data: Dict, verbose: bool = False, save_callback: callable = None) -> bool:
        """Search TMDB for all files in scan data."""
        try:
            if not self.tmdb_api_key:
                print("Please add a TMDB key")
                print("add tmdb <key>")
                return False

            if not scan_data:
                print("Please scan directories first")
                return False

            # Count files that need processing
            total_files = 0
            files_to_process = 0
            
            for directory in scan_data:
                for file_name, file_data in scan_data[directory].items():
                    total_files += 1
                    if not file_data.get("banned", False) and not file_data.get("tmdb"):
                        files_to_process += 1

            if files_to_process == 0:
                print("✓ All files already have TMDB data")
                return True

            print(f"Searching TMDB for {files_to_process} files (skipping {total_files - files_to_process} already processed)")
            
            # Track statistics
            stats = {
                "processed": 0,
                "matches_found": 0,
                "no_matches": 0,
                "banned_low_votes": 0,
                "skipped_banned": 0,
                "skipped_existing": 0,
                "fuzzy_matches": [],  # Store low-confidence matches for review
                "year_mismatches": []
            }

            for directory in scan_data:
                if verbose:
                    print(f"\nProcessing directory: {directory}")

                for file_name, file_data in scan_data[directory].items():
                    # Debug: Check what we're seeing for banned/tmdb files
                    if verbose:
                        banned_status = file_data.get("banned", False)
                        tmdb_status = file_data.get("tmdb")
                        if banned_status or tmdb_status:
                            print(f"  🔍 Checking: '{file_data.get('title', file_name)}' - Banned: {banned_status}, TMDB: {tmdb_status}")
                    
                    if file_data.get("banned", False):
                        if verbose:
                            print(f"  ⏭️  Skipping banned: '{file_data.get('title', file_name)}'")
                        stats["skipped_banned"] += 1
                        continue

                    if file_data.get("tmdb"):
                        if verbose:
                            print(f"  ⏭️  Skipping (has TMDB): '{file_data.get('title', file_name)}'")
                        stats["skipped_existing"] += 1
                        continue

                    if verbose:
                        print(f"  🎬 Processing: '{file_data.get('title', file_name)}'")

                    stats["processed"] += 1
                    result = self._search_tmdb_for_single_file(file_data, verbose, stats)
                    
                    # Save progress after each file
                    if save_callback:
                        try:
                            save_callback(scan_data)
                            if verbose:
                                print(f"    💾 Progress saved")
                        except Exception as e:
                            print(f"    ⚠️  Warning: Failed to save progress: {e}")
                    
                    # Progress indicator
                    if stats["processed"] % 10 == 0 or stats["processed"] == files_to_process:
                        percentage = (stats["processed"] / files_to_process) * 100
                        print(f"Progress: {stats['processed']}/{files_to_process} ({percentage:.1f}%)")

            # Print summary
            self._print_tmdb_summary(stats, verbose)
            return True
            
        except Exception as e:
            print(f"Error searching TMDB: {e}")
            return False

    def _search_tmdb_for_single_file(self, file_data: Dict, verbose: bool = False, stats: Dict = None):
        """Search TMDB for a single file."""
        title = file_data.get("title", "")
        year = file_data.get("year", "")

        # Clean title for search
        clean_title = title.strip()
        secondary_title = None
        if " aka " in clean_title.lower():
            titles = clean_title.lower().split(" aka ")
            clean_title = titles[0].strip()
            secondary_title = titles[1].strip() if len(titles) > 1 else None

        try:
            results = self._make_tmdb_search_request(clean_title, year)

            if not results:
                if verbose:
                    print(f"  ✗ No TMDB results for: '{title}'")
                file_data["banned"] = True
                if stats:
                    stats["no_matches"] += 1
                return

            # Process results
            for result in results:
                if self._is_low_vote_count(result):
                    if verbose:
                        vote_count = result.get("vote_count", 0)
                        print(f"  ⚠ Low vote count ({vote_count}) for: '{title}' -> '{result.get('title', '')}'")
                    file_data["banned"] = True
                    if stats:
                        stats["banned_low_votes"] += 1
                    continue

                match_result = self._is_title_match(result, clean_title=clean_title, secondary_title=secondary_title, verbose=verbose)
                if match_result:
                    match_score, match_info = match_result
                    self._update_file_with_tmdb_data(file_data, result, match_score, match_info)
                    
                    if stats:
                        stats["matches_found"] += 1
                        
                        # Track fuzzy matches for review
                        if match_score < 90:
                            stats["fuzzy_matches"].append({
                                "file_title": title,
                                "tmdb_title": result.get("title", ""),
                                "score": match_score,
                                "match_type": match_info
                            })
                        
                        # Track year mismatches
                        if year and result.get("release_date"):
                            tmdb_year_match = re.search(r"\d{4}", result["release_date"])
                            if tmdb_year_match:
                                tmdb_year = tmdb_year_match.group()
                                if year != tmdb_year:
                                    stats["year_mismatches"].append({
                                        "title": title,
                                        "file_year": year,
                                        "tmdb_year": tmdb_year
                                    })
                    
                    if verbose:
                        confidence = "High" if match_score >= 90 else "Medium" if match_score >= 80 else "Low"
                        print(f"  ✓ {confidence} confidence match ({match_score}%): '{title}' -> '{result.get('title', '')}'")
                    
                    break
            else:
                if verbose:
                    print(f"  ✗ No suitable match found for: '{title}'")
                if stats:
                    stats["no_matches"] += 1

        except Exception as e:
            print(f"  ✗ Error searching TMDB for '{title}': {e}")
            if stats:
                stats["no_matches"] += 1

    def _make_tmdb_search_request(self, clean_title: str, year: str = "") -> Optional[list]:
        """Make TMDB API search request."""
        url = "https://api.themoviedb.org/3/search/movie"
        query = quote(clean_title)
        params = {
            "api_key": self.tmdb_api_key,
            "query": query,
            "include_adult": "true",
            "language": "en-US",
            "page": 1,
        }

        if year:
            params["year"] = year

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = json.loads(response.content)
        return data.get("results", [])

    def _is_low_vote_count(self, result: Dict) -> bool:
        """Check if TMDB result has too low vote count."""
        vote_count = result.get("vote_count", 0)
        return vote_count <= MIN_VOTE_COUNT

    def _is_title_match(
        self,
        result: Dict,
        clean_title: str,
        secondary_title: str = None,
        verbose: bool = False,
    ) -> Optional[tuple]:
        """Check if TMDB result matches the file title.

        Compare each TMDB title variant (title, original_title) against the
        filename-derived primary title and, if present, the secondary title
        (e.g. extracted from "aka"). The secondary title is NOT treated as a
        candidate by itself; it is only compared against TMDB titles.

        Returns (match_score, match_info) tuple if match found, None otherwise.
        """
        def _norm(s: str) -> str:
            if not s:
                return ""
            s = re.sub(r"[^0-9A-Za-z\s]", " ", s)  # remove punctuation
            s = re.sub(r"\s+", " ", s).strip().lower()  # collapse whitespace + lower
            return s

        normalized_primary = _norm(clean_title)
        normalized_secondary = _norm(secondary_title) if secondary_title else None

        # TMDB title candidates (normalized)
        tmdb_title = result.get("title") or ""
        tmdb_og_title = result.get("original_title") or ""
        candidates = []
        if tmdb_title:
            candidates.append(("title", _norm(tmdb_title)))
        if tmdb_og_title and _norm(tmdb_og_title) != _norm(tmdb_title):
            candidates.append(("original_title", _norm(tmdb_og_title)))

        # compute scores: for each TMDB candidate compare against primary and (if present) secondary
        scored = []
        for label, cand in candidates:
            if not cand:
                continue
            score_primary = fuzz.token_set_ratio(cand, normalized_primary)
            scored.append((label, "primary", cand, score_primary))
            if normalized_secondary:
                score_secondary = fuzz.token_set_ratio(cand, normalized_secondary)
                scored.append((label, "secondary", cand, score_secondary))

        if not scored:
            return None

        # pick best scoring comparison
        best = max(scored, key=lambda x: x[3])
        best_label, best_kind, best_cand, best_score = best

        if best_score >= FUZZY_MATCH_THRESHOLD:
            match_info = f"{best_label}_{best_kind}"
            return (best_score, match_info)
        
        return None

    def _update_file_with_tmdb_data(self, file_data: Dict, tmdb_result: Dict, match_score: int = None, match_info: str = None):
        """Update file data with TMDB information."""
        tmdb_title = tmdb_result.get("title", "")
        tmdb_year = None

        if tmdb_result.get("release_date"):
            year_match = re.search(r"\d{4}", tmdb_result["release_date"])
            if year_match:
                tmdb_year = year_match.group().strip()

        file_data["tmdb"] = tmdb_result.get("id")
        file_data["tmdb_title"] = tmdb_title
        file_data["tmdb_year"] = tmdb_year
        
        # Save match quality information for debugging/quality assessment
        if match_score is not None:
            file_data["tmdb_match_score"] = match_score
        if match_info is not None:
            file_data["tmdb_match_info"] = match_info

    def get_tmdb_movie_details(self, tmdb_id: int) -> Dict:
        """Fetch detailed TMDB information for a movie."""
        try:
            url = f"https://api.themoviedb.org/3/movie/{tmdb_id}"
            params = {"api_key": self.tmdb_api_key}

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            return {
                "original_language": data.get("original_language"),
                "runtime": data.get("runtime"),
                "genres": data.get("genres", []),
                "overview": data.get("overview", ""),
                "popularity": data.get("popularity", 0),
            }
        except requests.RequestException as e:
            print(f"Error fetching TMDB details for ID {tmdb_id}: {e}")
            return {}

    def is_runtime_match(self, file_runtime: int, tmdb_runtime: int, delta: int = 5) -> bool:
        """Check if file runtime matches TMDB runtime within delta."""
        try:
            return abs(int(file_runtime) - int(tmdb_runtime)) <= delta
        except (ValueError, TypeError):
            return False

    def _print_tmdb_summary(self, stats: Dict, verbose: bool = False):
        """Print summary of TMDB search results."""
        print(f"\n📊 TMDB Search Summary:")
        print(f"  ✓ Successful matches: {stats['matches_found']}")
        print(f"  ✗ No matches found: {stats['no_matches']}")
        print(f"  ⚠ Banned (low votes): {stats['banned_low_votes']}")
        print(f"  → Skipped (already processed): {stats['skipped_existing']}")
        print(f"  → Skipped (banned): {stats['skipped_banned']}")
        
        # Show concerning matches that might need review
        if stats['fuzzy_matches'] and verbose:
            print(f"\n⚠ Low-confidence matches (review recommended):")
            for match in stats['fuzzy_matches'][:5]:  # Show top 5
                print(f"    {match['score']}% - '{match['file_title']}' -> '{match['tmdb_title']}'")
            if len(stats['fuzzy_matches']) > 5:
                print(f"    ... and {len(stats['fuzzy_matches']) - 5} more")
        
        if stats['year_mismatches'] and verbose:
            print(f"\n⚠ Year mismatches (review recommended):")
            for mismatch in stats['year_mismatches'][:5]:  # Show top 5
                print(f"    '{mismatch['title']}' - File: {mismatch['file_year']}, TMDB: {mismatch['tmdb_year']}")
            if len(stats['year_mismatches']) > 5:
                print(f"    ... and {len(stats['year_mismatches']) - 5} more")
        
        print()  # Empty line for spacing

#!/usr/bin/env python3
import os
import re
import csv
import sys
import traceback
import shlex
from .PTN.parse import PTN
import json
import requests
from thefuzz import fuzz
from urllib.parse import quote
import time
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from .mediainfo import get_media_info
from .settings import Settings

# Constants
TRACKER_MAP = {
    "aither": "ATH",
    "blutopia": "BLU",
    "fearnopeer": "FNP",
    "reelflix": "RFX",
    "lst": "LST",
    "onlyencodes": "OE",
    "ulcx": "ULCX",
}

SUPPORTED_EXTENSIONS = ["*.mkv"]
FUZZY_MATCH_THRESHOLD = 85
MIN_VOTE_COUNT = 5  # Minimum vote count on TMDB to consider as a match. This might be problematic with obscure films
PY_VERSION = "py" if sys.platform.startswith("win") else "python3"
# Quality mappings
QUALITY_MAPPINGS = {"bluray": "encode", "web": "webrip"}

ptn = PTN()


def parse_file(name: str) -> Dict[str, any]:
    return ptn.parse(name)


class UploadChecker:
    def __init__(self):
        self.settings = Settings()
        self._initialize_core_attributes()
        self._initialize_database_files()  # Create files first
        self._initialize_search_data()  # Then initialize data structures
        self._load_existing_data()  # Finally load existing data

    def _initialize_core_attributes(self):
        """Initialize core attributes and load settings."""
        self.term_size = os.get_terminal_size()
        self.output_folder = "outputs/"
        self.extract_filename = re.compile(r"^.*[\\\/](.*)")

        # Load settings and update instance attributes
        self.update_settings()

        # Load tracker info and other missing attributes
        self.tracker_info = self.settings.tracker_info
        self.data_folder = "data/"

        # Initialize empty data structures (will be loaded later)
        self.scan_data = {}
        self.search_data = {}

        # Ensure output folder exists
        Path(self.output_folder).mkdir(exist_ok=True)
        Path(self.data_folder).mkdir(exist_ok=True)

    def _initialize_search_data(self):
        """Initialize search data for enabled sites."""
        try:
            for tracker in self.enabled_sites:
                self.search_data[tracker] = {
                    "safe": {},
                    "risky": {},
                    "danger": {},
                }
        except Exception as e:
            print("Error loading enabled sites ", e)

    def _initialize_database_files(self):
        """Create database files if they don't exist."""
        try:
            database_file = Path(self.data_folder) / "database.json"
            search_data_file = Path(self.data_folder) / "search_data.json"

            for file_path, default_data in [
                (database_file, {}),
                (search_data_file, self.search_data),
            ]:
                if not file_path.exists():
                    file_path.parent.mkdir(exist_ok=True)
                    with open(file_path, "w") as outfile:
                        json.dump(default_data, outfile)

            self.database_location = str(database_file)
            self.search_data_location = str(search_data_file)
        except Exception as e:
            print(f"Error initializing json files: {e}")

    def _load_existing_data(self):
        """Load existing data from JSON files."""
        try:
            for file_path, target_attr in [
                (self.database_location, "scan_data"),
                (self.search_data_location, "search_data"),
            ]:
                if os.path.exists(file_path) and os.path.getsize(file_path) > 10:
                    with open(file_path, "r") as file:
                        setattr(self, target_attr, json.load(file))
        except Exception as e:
            print(f"Error loading json files: {e}")

    # Scan given directories
    def scan_directories(self, verbose=False):
        """Scan given directories for media files."""
        try:
            print("Scanning Directories")
            if not self._validate_directories():
                return False

            for directory in self.directories:
                self._scan_single_directory(directory, verbose)

            self.save_database()
            return True
        except Exception as e:
            print(f"Error scanning directories: {e}")
            return False

    def _validate_directories(self) -> bool:
        """Validate that directories are configured."""
        if not self.directories:
            print("Please add a directory")
            print("setting-add -t dir -s <dir>")
            return False
        return True

    def _scan_single_directory(self, dir: str, verbose=False):
        """Scan a single directory for media files."""
        dir_data = self.scan_data.get(dir, {})

        files = self._get_media_files(dir)
        for file_path in files:
            if self._should_skip_file(file_path, dir_data, verbose):
                continue

            file_data = self._process_media_file(file_path, verbose)
            if file_data:
                dir_data[file_data["file_name"]] = file_data

        self.scan_data[dir] = dir_data

    def _get_media_files(self, dir: str) -> List[str]:
        """Get all media files in directory."""
        files = []
        dir_path = Path(dir)
        for pattern in SUPPORTED_EXTENSIONS:
            # Remove the * from pattern since rglob expects just the extension
            extension = pattern.replace("*", "")
            files.extend(str(p) for p in dir_path.rglob(f"*{extension}"))
        return files

    def _should_skip_file(self, file_path: str, dir_data: dict, verbose: bool) -> bool:
        """Check if file should be skipped."""
        file_name = self.extract_filename.match(file_path).group(1)

        if file_name in dir_data:
            if verbose:
                print(f"{file_name} already exists in database.")
            return True
        return False

    def _process_media_file(self, file_path: str, verbose: bool) -> Optional[Dict]:
        """Process a single media file and extract metadata."""
        try:
            file_name = self.extract_filename.match(file_path).group(1)
            file_size = self.convert_size(os.path.getsize(file_path))

            if verbose:
                print("=" * self.term_size.columns)
                print(f"Scanning: {file_path}")
                print(f"File size: {file_size}")

            parsed_data = self._parse_filename(file_name, verbose)

            return {
                "file_location": file_path,
                "file_name": file_name,
                "file_size": file_size,
                "banned": parsed_data.get("banned", False),
                **parsed_data,
            }
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            return None

    def _parse_filename(self, file_name: str, verbose: bool) -> Dict:
        """Parse filename to extract metadata."""
        parsed = parse_file(file_name)

        title, year = self._extract_title_and_year(parsed, file_name, verbose)
        quality = self._normalize_quality(parsed.get("quality"))
        return {
            "title": title,
            "year": year,
            "quality": quality,
            "resolution": (
                parsed.get("resolution", "").strip()
                if parsed.get("resolution")
                else None
            ),
            "codec": parsed.get("codec"),
            "group": parsed.get("group"),
            "tmdb": None,
        }

    def _extract_title_and_year(
        self, parsed: dict, file_name: str, verbose: bool
    ) -> Tuple[str, str]:
        """Extract title and year from parsed data."""
        title = parsed.get("title", "").strip()
        year = str(parsed["year"]).strip() if parsed.get("year") else ""

        # Extract year from title if parser failed
        if not year:
            year_match = re.search(r"\d{4}", title)
            if year_match:
                year = year_match.group().strip()
                title = re.sub(r"[\d]{4}", "", title).strip()
                if verbose:
                    print(f"Year manually extracted from title: {title}, {year}")

        return title, year

    def _normalize_quality(self, quality: str) -> Optional[str]:
        """Normalize quality string."""
        if not quality:
            return None

        clean_quality = re.sub(r"[^a-zA-Z]", "", quality).strip().lower()
        return QUALITY_MAPPINGS.get(clean_quality, clean_quality)

    # Get the tmdbId
    def get_tmdb(self, verbose=False):
        try:
            if not self.scan_data:
                print("Please scan directories first")
                return False
            print("Searching TMDB")
            if not self.tmdb_key:
                print("Please add a TMDB key")
                print("setting-add -t tmdb -s <key>")
                return False
            for dir in self.scan_data:
                if verbose:
                    print("Searching files from: ", dir)
                for key, value in self.scan_data[dir].items():
                    if value["banned"]:
                        continue
                    if value["tmdb"]:
                        if value["tmdb"] and verbose:
                            print(value["title"], " Already searched on TMDB.")
                        continue

                    title = value["title"]
                    if verbose:
                        print("=" * self.term_size.columns)
                        print(f"Searching TMDB for {title}")
                    year = value["year"] if value["year"] else ""
                    # This seems possibly problematic
                    clean_title = re.sub(r"[^0-9a-zA-Z]", " ", title)
                    query = quote(clean_title)
                    try:
                        url = f"https://api.themoviedb.org/3/search/movie"
                        params = {
                            "api_key": self.tmdb_key,
                            "query": query,
                            "include_adult": "true",
                            "language": "en-US",
                            "page": 1,
                        }
                        params["year"] = year if year else None
                        res = requests.get(url, params=params, timeout=10)
                        data = json.loads(res.content)
                        results = data["results"] if "results" in data else None
                        if not results:
                            if verbose:
                                print("No results, Banning.")
                            value["banned"] = True
                            self.save_database()
                            continue
                        for r in results:
                            if "vote_count" in r and r["vote_count"] <= MIN_VOTE_COUNT:
                                value["banned"] = True
                                self.save_database()
                                continue

                            tmdb_title = r["title"]
                            tmdb_year = (
                                re.search(r"\d{4}", r["release_date"]).group().strip()
                                if r["release_date"]
                                else None
                            )
                            match = fuzz.ratio(tmdb_title, clean_title)
                            if verbose:
                                print(
                                    "attempting to match result: ",
                                    tmdb_title,
                                    "with: ",
                                    title,
                                )
                            if match >= 85:
                                id = r["id"]
                                value["tmdb"] = id
                                value["tmdb_title"] = tmdb_title
                                value["tmdb_year"] = tmdb_year
                                if verbose:
                                    print("Match successful")
                                break
                        if verbose and not value["tmdb"]:
                            print("Couldn't find a match.")
                    except Exception as e:
                        print(
                            f"Something went wrong when searching TMDB for {title}", e
                        )
                self.save_database()
            self.save_database()
            return True
        except Exception as e:
            print("Error searching TMDB: ", e)

    def _check_groups(self, verbose=False, file=None, tracker=None):
        banned_groups = self.tracker_info[tracker].get("bannedGroups", [])
        if not banned_groups:
            return False

        # Add null check for group
        if not file.get("group"):
            return False

        file_group = file["group"].lower()
        for bg in banned_groups:
            if bg.lower() in file_group:
                if verbose:
                    print(
                        f"Banning {file['file_name']} from {tracker} due to group {bg}"
                    )
                return True
        return False

    # Search trackers
    def search_trackers(self, verbose=False):
        try:
            print("Searching trackers")
            if not self._validate_api_keys():
                return False

            for dir in self.scan_data:
                for key, value in self.scan_data[dir].items():
                    if not self._should_process_file(value):
                        continue

                    self._search_file_on_trackers(value, verbose)
                    self.save_database()

            self.save_database()
            return True
        except Exception as e:
            print("Error searching tracker: ", e)

    def _validate_api_keys(self):
        """Validate that all enabled trackers have API keys."""
        for tracker in self.enabled_sites:
            api_key = self.current_settings["keys"].get(tracker)
            if not api_key:
                print(f"No API key for {tracker} found.")
                print(
                    "If you want to use this tracker, add an API key to the settings."
                )
                if not input("Continue? [y/n] ").lower().startswith("y"):
                    return False
        return True

    def _should_process_file(self, file_data):
        """Check if file should be processed for tracker searches."""
        if file_data["banned"]:
            return False
        if file_data["tmdb"] is None:
            return False
        return True

    def _search_file_on_trackers(self, file_data, verbose=False):
        """Search a single file across all enabled trackers."""
        print("=" * self.term_size.columns)
        print(f"Searching Trackers for {file_data['title']}")
        if verbose:
            print(f"Filename: {file_data['file_name']}")

        if "trackers" not in file_data:
            file_data["trackers"] = {}

        for tracker in self.enabled_sites:
            try:
                result = self._search_single_tracker(file_data, tracker, verbose)
                file_data["trackers"][tracker] = result  # This stores the result

                if verbose:
                    self._print_tracker_result(tracker, result)

            except Exception as e:
                print(f"Error searching {tracker} for {file_data['title']}: {e}")

        print("Waiting for cooldown...", self.cooldown, "seconds")
        time.sleep(self.cooldown)

    def _search_single_tracker(self, file_data, tracker, verbose=False):
        """Search a single tracker for a file. Returns the result message."""

        # Skip if already searched
        if tracker in file_data["trackers"]:
            if verbose:
                print(f"{tracker} already searched for {file_data['title']}. Skipping.")
            return file_data["trackers"][tracker]

        # Check if API key exists
        api_key = self.current_settings["keys"].get(tracker)

        # Check banned groups FIRST - before making API call
        if self._check_groups(verbose=verbose, file=file_data, tracker=tracker):
            return "Banned group"

        # Make API request
        url = f"{self.tracker_info[tracker]['url']}api/torrents/filter"
        params = {
            "tmdbId": file_data["tmdb"],
            "categoriesIds[]": 1,
            "api_token": api_key,
        }

        all_results = []
        while url:
            response = requests.get(url, params=params)
            res_data = json.loads(response.content)
            results = res_data.get("data", [])
            all_results.extend(results)

            # Check for pagination
            links = res_data.get("links", {})
            next_url = links.get("next")
            if next_url:
                url = next_url
                params = None  # Params are already included in next_url
            else:
                url = None

        # Handle results
        return self._process_tracker_results(all_results, file_data, tracker)

    def _process_tracker_results(self, results, file_data, tracker):
        """Process tracker API results and return appropriate message."""

        # No results found
        if not results:
            return False  # Not on tracker

        # Analyze results for quality/resolution matches
        file_quality = file_data.get("quality")
        file_resolution = file_data.get("resolution")

        quality_matches = []

        for result in results:
            info = result["attributes"]
            tracker_resolution = info["resolution"]
            tracker_quality = re.sub(r"[^a-zA-Z]", "", info["type"]).strip()
            resolution_match = self._check_resolution_match(
                file_resolution, tracker_resolution
            )
            quality_match = self._check_quality_match(file_quality, tracker_quality)
            # Exact match found
            if resolution_match and quality_match:
                return True  # Exact dupe

            # Store partial matches for analysis
            if resolution_match:
                quality_matches.append(tracker_quality.lower())
        # Analyze partial matches
        return self._analyze_partial_matches(
            quality_matches, file_quality, file_resolution, tracker
        )

    def _check_resolution_match(self, file_resolution, tracker_resolution):
        """Check if resolutions match."""
        if not file_resolution:
            return False

        clean_file_res = "".join(re.findall(r"\d+", file_resolution))
        clean_tracker_res = "".join(re.findall(r"\d+", tracker_resolution))

        return clean_file_res == clean_tracker_res

    def _check_quality_match(self, file_quality, tracker_quality):
        """Check if qualities match."""
        if not file_quality:
            return False
        # Rename disc to match quality hierarchy
        if "disc" in tracker_quality.lower():
            tracker_quality = "fulldisc"
        return file_quality.lower() == tracker_quality.lower()

    def _analyze_partial_matches(
        self, quality_matches, file_quality, file_resolution, tracker
    ):
        """Analyze partial matches and return appropriate message."""

        if not quality_matches:
            return f"Safe: New release. {file_quality or ''} {file_resolution or ''}"

        if not file_quality:
            return f"Danger: Source found on {tracker}, but couldn't determine file quality. Manual search required."

        # Check if this would be an upgrade
        is_upgrade = all(
            self.settings.is_upgrade(file_quality, existing_quality)
            for existing_quality in quality_matches
        )

        if is_upgrade:
            return f"Safe: Resolution found on {tracker}, but seems like an upgrade. {file_quality}"
        else:
            # This means the quality is likely a downgrade to existing.
            return f"Risky: Resolution found on {tracker}, but could be a new quality. Manual search recommended."

    def _print_tracker_result(self, tracker, result):
        """Print tracker search result in a readable format."""
        if result is True:
            print(f"Already on {tracker}")
        elif result is False:
            print(f"Not on {tracker}")
        elif result == "Banned group":
            print(f"Banned group on {tracker}")
        else:
            print(f"{tracker}: {result}")

    # Create search_data.json
    def create_search_data(self, mediainfo=True):
        """Create search data by processing scan results and categorizing by safety level."""
        try:
            print("Creating search data.")

            for dir in self.scan_data:
                for key, value in self.scan_data[dir].items():
                    if self._should_skip_file_for_search_data(value):
                        continue

                    # Extract media info once if needed
                    file_location = value["file_location"]
                    media_info = get_media_info(file_location)
                    self.scan_data[dir][key]["media_info"] = media_info
                    # Process each tracker result
                    for tracker, tracker_result in value["trackers"].items():
                        try:
                            self._process_tracker_for_search_data(
                                value, tracker, tracker_result, media_info
                            )
                        except Exception as e:
                            print(
                                f"Error processing {tracker} for {value['title']}: {e}"
                            )
            self.save_database()
            self.save_search_data()

        except Exception as e:
            print("Error creating search_data.json", e)

    def _should_skip_file_for_search_data(self, file_data):
        """Check if file should be skipped during search data creation."""
        if file_data["banned"]:
            return True
        if "trackers" not in file_data:
            return True
        return False

    def _process_tracker_for_search_data(
        self, file_data, tracker, tracker_result, media_info
    ):
        """Process a single tracker result for search data."""
        # Skip exact dupes
        if tracker_result is True or (
            isinstance(tracker_result, str) and "Dupe!" in tracker_result
        ):
            return

        # Create tracker info
        tracker_info = self._build_tracker_info(file_data, tracker_result, media_info)

        # Determine safety category
        safety_category = self._determine_safety_category(
            file_data, tracker_result, media_info
        )

        # Add to search data
        title = file_data["title"]
        self.search_data[tracker][safety_category][title] = tracker_info

    def _build_tracker_info(self, file_data, tracker_result, media_info):
        """Build the tracker info dictionary."""

        # Normalize the message
        if isinstance(tracker_result, bool):
            message = f"Not on tracker" if tracker_result is False else "Dupe!"
        else:
            message = str(tracker_result).strip()

        # Check for extra info conditions
        extra_info = self._build_extra_info(file_data, media_info)

        return {
            "file_location": file_data["file_location"],
            "year": file_data["year"],
            "quality": file_data["quality"],
            "resolution": file_data["resolution"],
            "tmdb": file_data["tmdb"],
            "tmdb_year": file_data["tmdb_year"],
            "message": message,
            "file_size": file_data["file_size"],
            "extra_info": extra_info,
            "media_info": media_info,
        }

    def _build_extra_info(self, file_data, media_info):
        """Build extra info string based on various conditions."""
        extra_info_parts = []

        # Check year mismatch
        if file_data["year"] != file_data["tmdb_year"]:
            extra_info_parts.append(
                "TMDB Release year and given year are different this might mean improper match manual search required"
            )

        # Check English language/subtitles
        if media_info and self._has_no_english_content(media_info):
            extra_info_parts.append("No English subtitles found in media info")

        return " ".join(extra_info_parts)

    def _has_no_english_content(self, media_info):
        """Check if media has no English audio or subtitles."""
        audio_languages = media_info.get("audio_language(s)", [])
        subtitles = media_info.get("subtitle(s)", [])

        has_english_audio = any(lang.startswith("en") for lang in audio_languages)
        has_english_subs = any(sub.startswith("en") for sub in subtitles)

        return not has_english_audio and not has_english_subs

    def _is_runtime_match(self, file_runtime, tmdb_runtime, delta=5):
        try:
            return abs(int(file_runtime) - int(tmdb_runtime)) <= delta
        except (ValueError, TypeError):
            return False

    def _get_tmdb_info(self, tmdb_id):
        """Fetch TMDB information for a given ID."""
        try:
            url = f"https://api.themoviedb.org/3/movie/"
            response = requests.get(
                f"{url}{tmdb_id}", params={"api_key": self.tmdb_key}
            )
            response.raise_for_status()
            info = {
                "original_language": response.json().get("original_language"),
                "runtime": response.json().get("runtime"),
            }
            return info
        except requests.RequestException as e:
            print(f"Error fetching TMDB info: {e}")
            return {}

    def _handle_year_mismatch(self, file_data, media_info):
        # Year mismatch logic
        year_match = False
        runtime_match = False
        language_match = False

        file_year = file_data.get("year")
        tmdb_year = file_data.get("tmdb_year")
        file_runtime = file_data.get("media_info", {}).get("runtime")
        tmdb_id = file_data.get("tmdb")

        # Check year delta
        if file_year and tmdb_year:
            try:
                year_diff = abs(int(file_year) - int(tmdb_year))
                if year_diff <= 1:
                    year_match = True
            except ValueError:
                pass

        # Get TMDB info for runtime and language
        info = self._get_tmdb_info(tmdb_id) if tmdb_id else {}
        if info:
            # Runtime check
            runtime_match = self._is_runtime_match(file_runtime, info.get("runtime"))
            # Language check
            tmdb_lang = info.get("original_language")
            media_langs = media_info.get("audio_language(s)", []) if media_info else []
            if tmdb_lang and any(lang.startswith(tmdb_lang) for lang in media_langs):
                language_match = True

        # Decision logic
        checks = [year_match, runtime_match, language_match]

        safety_checks = sum(checks)
        return safety_checks

    def _determine_safety_category(self, file_data, tracker_result, media_info):
        """Determine the safety category (safe/risky/danger) for the file."""

        # No English content = danger
        # Most tracker require either English audio or subtitles
        if media_info and self._has_no_english_content(media_info):
            return "danger"

        # Year mismatch
        if file_data["year"] != file_data["tmdb_year"]:
            print(
                f"Year mismatch for {file_data['title']}: {file_data['year']} vs {file_data['tmdb_year']}"
            )
            print("Verifying mismatch...")
            safety_checks = self._handle_year_mismatch(file_data, media_info)
            if safety_checks == 3:
                print(f"All mismatch checks passed for {file_data['title']}: Safe")
                return "safe"
            elif safety_checks == 2:
                print(f"Some mismatch checks passed for {file_data['title']}: Risky")
                return "risky"
            else:
                print(f"All mismatch checks failed for {file_data['title']}: Danger")
                return "danger"

        # Analyze tracker result
        if isinstance(tracker_result, bool):
            return "safe" if tracker_result is False else "danger"

        # String-based categorization
        result_lower = str(tracker_result).lower()
        if "safe" in result_lower:
            return "safe"
        if "danger" in result_lower:
            return "danger"
        if "risky" in result_lower:
            return "risky"

        return "danger"

    def _build_command_line(
        self, py_version: str, script_path: Path, *args: str
    ) -> str:
        cmd = [py_version, str(script_path), *args]
        return " ".join(shlex.quote(arg) for arg in cmd)

    def export_gg(self):
        """Exports results as commands ready to use for uploading with gg_bot."""
        try:
            if not self.gg_path:
                print("gg_path not configured.")
                return

            gg_dir = Path(self.gg_path)
            if gg_dir.name == "auto_upload.py":
                gg_dir = gg_dir.parent

            py_version = PY_VERSION
            script_path = gg_dir / "auto_upload.py"

            for tracker, data in self.search_data.items():
                out_path = Path(self.output_folder) / f"{tracker}_gg.txt"
                tracker_flag = TRACKER_MAP[tracker]

                with out_path.open("w") as f:
                    for category in (
                        ("safe", "risky") if self.settings["allow_risky"] else ("safe",)
                    ):
                        for value in data.get(category, {}).values():
                            line = self._build_command_line(
                                py_version,
                                script_path,
                                "-p",
                                value["file_location"],
                                "-t",
                                tracker_flag,
                            )
                            f.write(line + "\n")

                print(f"Exported gg-bot auto_upload commands to {out_path}")

        except Exception as e:
            print(f"Error exporting gg-bot commands: {e}")

    def export_ua(self):
        """Exports results as commands ready to use for uploading with upload assistant."""
        try:
            if not self.ua_path:
                print("ua_path not configured.")
                return

            ua_dir = Path(self.ua_path)
            if ua_dir.name == "upload.py":
                ua_dir = ua_dir.parent

            py_version = PY_VERSION
            script_path = ua_dir / "upload.py"
            for tracker, data in self.search_data.items():
                out_path = Path(self.output_folder) / f"{tracker}_ua.txt"
                tracker_flag = TRACKER_MAP[tracker]
                with out_path.open("w") as f:
                    for category in (
                        ("safe", "risky")
                        if self.current_settings.get("allow_risky")
                        else ("safe",)
                    ):
                        for value in data.get(category, {}).values():
                            line = self._build_command_line(
                                py_version,
                                script_path,
                                "--trackers",
                                tracker_flag,
                                value["file_location"],
                            )
                            f.write(line + "\n")

                print(f"Exported Upload-Assistant commands to {out_path}")

        except Exception as e:
            print(f"Error exporting Upload-Assistant commands: {e}")

    # Export possible uploads to manual.txt
    def export_txt(self):
        try:
            # Loop through each tracker to output separate files
            for tracker, data in self.search_data.items():
                with open(f"{self.output_folder}{tracker}_uploads.txt", "w") as f:
                    f.write("")
                # Loop through each safety/danger/risky/etc. section
                for safety, d in data.items():
                    if d:
                        with open(
                            f"{self.output_folder}{tracker}_uploads.txt", "a"
                        ) as file:
                            file.write(safety + "\n")
                    # Loop through each file in the section
                    for k, v in d.items():
                        title = k
                        url_query = quote(title)
                        file_location = v["file_location"]
                        quality = v["quality"]
                        tmdb = v["tmdb"]
                        info = v["message"]
                        file_size = v["file_size"]
                        extra_info = v["extra_info"] if v["extra_info"] else ""
                        tmdb_year = v["tmdb_year"]
                        year = v["year"]
                        tmdb_search = f"https://www.themoviedb.org/movie/{tmdb}"
                        tracker_url = self.tracker_info[tracker]["url"]
                        tracker_tmdb = f"{tracker_url}torrents?view=list&tmdbId={tmdb}"
                        tracker_string = (
                            f"{tracker_url}torrents?view=list&name={url_query}"
                        )
                        media_info = v["media_info"] if "media_info" in v else "None"
                        clean_mi = ""
                        if media_info:
                            (
                                audio_language,
                                subtitles,
                                video_info,
                                audio_info,
                                hdr_type,
                                runtime,
                            ) = media_info.values()
                            clean_mi = f"""
            Language(s): {audio_language}
            Subtitle(s): {subtitles}
            Audio Info: {audio_info}
            Video Info: {video_info}
            HDR Type: {hdr_type}
            Duration: {runtime} min
                            """
                        line = f"""
        Movie Title: {title}
        File Year: {year}
        TMDB Year: {tmdb_year}
        Quality: {quality}
        File Location: {file_location}
        File Size: {file_size}
        TMDB Search: {tracker_tmdb}
        String Search: {tracker_string}
        TMDB: {tmdb_search}
        Search Info: {info}
        Extra Info: {extra_info}
        Media Info: {clean_mi}
        """
                        with open(
                            f"{self.output_folder}{tracker}_uploads.txt", "a"
                        ) as f:
                            f.write(line + "\n")
                print(f"Manual info saved to {self.output_folder}{tracker}_uploads.txt")
        except Exception as e:
            print("Error writing uploads.txt: ", e)
            print(traceback.format_exc())

    def export_csv(self):
        try:
            for tracker, data in self.search_data.items():
                with open(
                    f"{self.output_folder}{tracker}_uploads.csv",
                    "w",
                    newline="",
                    encoding="utf-8",
                ) as csvfile:
                    fieldnames = [
                        "Safety",
                        "Movie Title",
                        "TMDB Year",
                        "Extra Info",
                        "Search Info",
                        "Quality",
                        "File Location",
                        "File Size",
                        "TMDB Search",
                        "String Search",
                        "TMDB",
                        "Media Info",
                        "File Year",
                    ]
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    if data:
                        for safety, d in data.items():
                            for k, v in d.items():
                                title = k
                                url_query = quote(title)
                                file_location = v["file_location"]
                                quality = v["quality"]
                                tmdb = v["tmdb"]
                                info = v["message"]
                                file_size = v["file_size"]
                                extra_info = v["extra_info"] if v["extra_info"] else ""
                                tmdb_year = v["tmdb_year"]
                                year = v["year"]
                                tmdb_search = f"https://www.themoviedb.org/movie/{tmdb}"
                                tracker_url = self.tracker_info[tracker]["url"]
                                tracker_tmdb = (
                                    f"{tracker_url}torrents?view=list&tmdbId={tmdb}"
                                )
                                tracker_string = (
                                    f"{tracker_url}torrents?view=list&name={url_query}"
                                )
                                media_info = (
                                    v["media_info"] if v["media_info"] else "None"
                                )
                                clean_mi = ""
                                if media_info:

                                    (
                                        audio_language,
                                        subtitles,
                                        video_info,
                                        audio_info,
                                        hdr_type,
                                        runtime,
                                    ) = media_info.values()
                                    clean_mi = f"Language(s): {audio_language}, Subtitle(s): {subtitles}, Audio Info: {audio_info}, Video Info: {video_info}, HDR Type: {hdr_type}, Duration: {runtime} min"

                                writer.writerow(
                                    {
                                        "Safety": safety,
                                        "Movie Title": title,
                                        "File Year": year,
                                        "TMDB Year": tmdb_year,
                                        "Quality": quality,
                                        "File Location": file_location,
                                        "File Size": file_size,
                                        "TMDB Search": tracker_tmdb,
                                        "String Search": tracker_string,
                                        "TMDB": tmdb_search,
                                        "Search Info": info,
                                        "Extra Info": extra_info,
                                        "Media Info": clean_mi,
                                    }
                                )
            print(f"Manual info saved to {self.output_folder}{tracker}_uploads.csv")
        except Exception as e:
            print("Error writing uploads.csv: ", e)

    # Update database.json
    def save_database(self):
        try:
            with open(self.database_location, "w") as of:
                json.dump(self.scan_data, of)
        except Exception as e:
            print("Error writing to database.json: ", e)

    # Update search_data.json
    def save_search_data(self):
        try:
            with open(self.search_data_location, "w") as of:
                json.dump(self.search_data, of)
        except Exception as e:
            print("Error writing to tracker_data.json: ", e)

    def clear_data(self):
        """Clear all stored data from JSON files."""
        try:
            # Clear search data with proper structure
            empty_search_data = {}
            for tracker in self.enabled_sites:
                empty_search_data[tracker] = {
                    "safe": {},
                    "risky": {},
                    "danger": {},
                }

            with open(self.search_data_location, "w") as of:
                json.dump(empty_search_data, of)
            with open(self.database_location, "w") as of:
                json.dump({}, of)

            # Reset instance variables
            self.scan_data = {}
            self.search_data = empty_search_data

            print("Data cleared!")
        except Exception as e:
            print("Error clearing json data: ", e)

    def run_all(self, mediainfo=True, verbose=False):
        """Run the complete workflow: scan -> tmdb -> search -> create data -> export."""
        try:
            print("Starting complete workflow...")

            # Step 1: Scan directories
            print("\n--- Step 1: Scanning Directories ---")
            if not self.scan_directories(verbose):
                print("Directory scanning failed. Aborting.")
                return False

            # Step 2: Get TMDB data
            print("\n--- Step 2: Getting TMDB Data ---")
            if not self.get_tmdb(verbose):
                print("TMDB search failed. Aborting.")
                return False

            # Step 3: Search trackers
            print("\n--- Step 3: Searching Trackers ---")
            if not self.search_trackers(verbose):
                print("Tracker search failed. Aborting.")
                return False

            # Step 4: Create search data
            print("\n--- Step 4: Creating Search Data ---")
            self.create_search_data(mediainfo)

            # Step 5: Export all formats
            print("\n--- Step 5: Exporting Results ---")
            self.export_gg()
            self.export_ua()
            self.export_txt()
            self.export_csv()

            print("\n Complete workflow finished successfully!")
            return True

        except Exception as e:
            print(f"Error in run_all workflow: {e}")
            return False

    # Settings functions
    def update_settings(self):
        self.current_settings = self.settings.current_settings
        self.directories = self.current_settings["directories"]
        self.tmdb_key = self.current_settings["tmdb_key"]
        self.enabled_sites = self.current_settings["enabled_sites"]
        self.cooldown = self.current_settings["search_cooldown"]
        self.minimum_size = self.current_settings["min_file_size"]
        self.ignore_qualities = self.current_settings["ignored_qualities"]
        self.ignore_keywords = self.current_settings["ignored_keywords"]
        self.gg_path = self.current_settings["gg_path"]
        self.ua_path = self.current_settings["ua_path"]

    def update_setting(self, target, value):
        self.settings.update_setting(target, value)
        self.update_settings()

    def get_setting(self, target):
        setting = self.settings.return_setting(target)
        if setting:
            print(setting)
        else:
            print("Not set yet.")

    def reset_setting(self):
        self.settings.reset_settings()
        self.update_settings()

    def remove_setting(self, target):
        self.settings.remove_setting(target)
        self.update_settings()

    def convert_size(self, size_bytes):
        if size_bytes == 0:
            return "0B"
        size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return "%s %s" % (s, size_name[i])

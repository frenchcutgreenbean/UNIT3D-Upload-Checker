import os
import json
import traceback
from pathlib import Path
from typing import Dict, List, Union, Optional
import requests


# CONSTANTS
DATA_FOLDER = Path("./data/")
SETTINGS_FILE = DATA_FOLDER / "settings.json"
TRACKER_INFO_FILE = Path("tracker_info.json")

DEFAULT_SETTINGS = {
    "directories": [],
    "tmdb_key": "",
    "enabled_sites": [],
    "keys": {
        "aither": "",
        "blutopia": "",
        "fearnopeer": "",
        "reelflix": "",
        "lst": "",
        "ulcx": "",
        "onlyencodes": "",
    },
    "gg_path": "",  # Path to GG-Bot e.g. /home/user/gg-bot-upload-assistant/ --- Not required only for export_gg_bot()
    "ua_path": "",  # Path to upload-assistant, e.g. /home/user/uplaad-assistant/ --- Optional
    "search_cooldown": 5,  # In seconds, how long to wait between each tracker search. 30 requests per minute is max before hit rate limits. - HDVinnie
    "min_file_size": 800,  # Minimum file size in MB to consider a torrent
    "ignored_qualities": ["dvdrip", "bdrip", "cam", "ts", "telesync", "hdtv", "webrip"],
    "ignored_keywords": [],  # Keywords to ignore in torrent names e.g. "fanedit", "screener" etc.
}

# Patterns for easy CLI access to tracker nicknames
# These are used to map nicknames to actual tracker names
TRACKER_NICKNAMES = {
    "fnp": "fearnopeer",
    "fearnopeer": "fearnopeer",
    "reelflix": "reelflix",
    "rfx": "reelflix",
    "aither": "aither",
    "aith": "aither",
    "blu": "blutopia",
    "blutopia": "blutopia",
    "lst": "lst",
    "lstgg": "lst",
    "ulcx": "ulcx",
    "upload.cx": "ulcx",
    "onlyencodes": "onlyencodes",
    "oe": "onlyencodes",
}

# Quality hierarchy for comparison
QUALITY_HIERARCHY = {"webrip": 0, "web-dl": 1, "encode": 2, "remux": 3}


class Settings:
    def __init__(self):
        self.data_folder = DATA_FOLDER
        self.default_settings = DEFAULT_SETTINGS
        self.tracker_nicknames = TRACKER_NICKNAMES
        self.quality_hierarchy = QUALITY_HIERARCHY
        self.current_settings = None
        self.tracker_info = None

        self._initialize_settings()
        self._load_tracker_info()

    def _initialize_settings(self):
        """Initialize settings file and load current settings."""
        try:
            self._ensure_settings_file_exists()
            self._load_current_settings()
            if not self.current_settings:
                self.current_settings = self.default_settings
        except Exception as e:
            print(f"Error initializing settings: {e}")

    def _ensure_settings_file_exists(self):
        """Create settings file with defaults if it doesn't exist or is empty."""
        if not SETTINGS_FILE.exists() or SETTINGS_FILE.stat().st_size < 10:
            self._write_json_file(SETTINGS_FILE, self.default_settings)

    def _load_current_settings(self):
        """Load settings from file if it's not empty."""
        if SETTINGS_FILE.stat().st_size > 10:
            self.current_settings = self._read_json_file(SETTINGS_FILE)
            if self.current_settings:
                self.validate_directories()

    def _load_tracker_info(self):
        """Load tracker info from JSON file."""
        if not self.tracker_info:
            self.tracker_info = self._read_json_file(TRACKER_INFO_FILE)

    # Clean directories from loaded settings
    def validate_directories(self):
        """Clean and validate directory paths."""
        try:
            directories = list(set(self.current_settings["directories"]))
            cleaned_dirs = self._clean_directory_paths(directories)
            filtered_dirs = self._remove_redundant_paths(cleaned_dirs)
            normalized_dirs = self._normalize_directory_paths(filtered_dirs)

            self.current_settings["directories"] = normalized_dirs
            self.write_settings()
        except Exception as e:
            print(f"Error validating directories: {e}")
            traceback.print_exc()

    def _clean_directory_paths(self, directories: List[str]) -> List[str]:
        """Remove trailing slashes and filter existing directories."""
        cleaned = []
        for dir_path in directories:
            clean_path = dir_path.rstrip("\\/")
            if os.path.exists(clean_path):
                cleaned.append(clean_path)
            else:
                print(f"{dir_path} does not exist, removing")
        return cleaned

    def _remove_redundant_paths(self, directories: List[str]) -> List[str]:
        """Remove child directories when parent is already included."""
        if len(directories) <= 1:
            return directories

        # Sort by length to process parents first
        sorted_dirs = sorted(directories, key=len)
        filtered = []

        for current_dir in sorted_dirs:
            is_redundant = any(
                current_dir.startswith(existing_dir + os.sep)
                for existing_dir in filtered
            )
            if not is_redundant:
                filtered.append(current_dir)

        return filtered

    def _normalize_directory_paths(self, directories: List[str]) -> List[str]:
        """Ensure all paths end with appropriate separator."""
        return [
            dir_path if dir_path.endswith(os.sep) else dir_path + os.sep
            for dir_path in directories
        ]

    def validate_tmdb(self, key: str) -> bool:
        """Validate TMDB API key."""
        try:
            url = "https://api.themoviedb.org/3/configuration"
            response = requests.get(url, params={"api_key": key}, timeout=10)

            if response.status_code == 200:
                self.current_settings["tmdb_key"] = key
                print("TMDB key is valid and was added")
                return True
            else:
                print("Invalid TMDB API Key")
                return False
        except Exception as e:
            print(f"Error validating TMDB API: {e}")
            return False

    def validate_key(self, key: str, target: str) -> bool:
        """Validate tracker API key."""
        tracker = self._get_tracker_from_nickname(target)
        if not tracker:
            print(f"{target} is not a supported site")
            return False

        if not self._test_tracker_api(tracker, key):
            print("Invalid API Key")
            return False

        self.current_settings["keys"][tracker] = key
        self.write_settings()
        print(f"Key is valid and was added to {tracker}")
        return True

    def _get_tracker_from_nickname(self, nickname: str) -> Optional[str]:
        """Get tracker name from nickname."""
        return self.tracker_nicknames.get(nickname)

    def _test_tracker_api(self, tracker: str, key: str) -> bool:
        """Test if tracker API key is valid."""
        try:
            test_params = {"perPage": 10, "api_token": key}
            url = f"{self.tracker_info[tracker]['url']}api/torrents"
            response = requests.get(url, params=test_params, timeout=10)
            return not response.history  # No redirect means valid key
        except Exception as e:
            print(f"Error testing tracker API: {e}")
            return False

    def setting_helper(self, target):
        settings = self.current_settings
        nicknames = self.tracker_nicknames
        matching_keys = [key for key in settings.keys() if target in key]
        matching_nicks = [nick for nick in nicknames.keys() if target in nick]
        if len(matching_nicks) >= 1:
            return False
        if len(matching_keys) == 1:
            return matching_keys[0]
        elif len(matching_keys) > 1:
            print(
                "Multiple settings match the provided substring. Please provide a more specific target."
            )
            print(settings.keys())
            print(
                "Unique substrings accepted: dir, tmdb, sites, gg, search, size, dupes, banned, qual, keywords"
            )
            print(
                "If you're trying to add a tracker key, you can use setting-add -t <site> -s <api_key>"
            )
            print("Accepted sites: ", nicknames.keys())
            return
        else:
            print(target, " is not a supported setting")
            print("Accepted targets: ", settings.keys())
            print(
                "Unique substrings accepted: dir, tmdb, sites, gg, search, size, dupes, banned, qual, keywords"
            )
            print(
                "If you're trying to add a tracker key, you can use setting-add -t <site> -s <api_key>"
            )
            print("Accepted sites: ", nicknames.keys())
            return

    def update_setting(self, target: str, value: str) -> bool:
        """Update a specific setting with improved structure."""
        try:
            # Handle tracker keys first
            if target in self.tracker_nicknames:
                return self._handle_tracker_key(target, value)

            # Get the actual setting key
            matching_key = self.setting_helper(target)
            if not matching_key:
                return False

            return self._update_setting_by_type(matching_key, value)

        except Exception as e:
            print(f"Error updating setting: {e}")
            traceback.print_exc()
            return False

    def _handle_tracker_key(self, target: str, value: str) -> bool:
        """Handle tracker API key updates."""
        if not value:
            print("No API key provided")
            return False
        return self.validate_key(value, target)

    def _update_setting_by_type(self, setting_key: str, value: str) -> bool:
        """Update setting based on its type."""
        current_value = self.current_settings[setting_key]

        # Dispatch to appropriate handler based on type
        type_handlers = {
            str: self._handle_string_setting,
            list: self._handle_list_setting,
            bool: self._handle_bool_setting,
            int: self._handle_int_setting,
        }

        handler = type_handlers.get(type(current_value))
        if not handler:
            print(f"Unsupported setting type: {type(current_value)}")
            return False

        success = handler(setting_key, value)
        if success:
            self.write_settings()
        return success

    def _handle_string_setting(self, setting_key: str, value: str) -> bool:
        """Handle string setting updates."""
        if setting_key == "tmdb_key":
            if self.validate_tmdb(value):
                self.current_settings[setting_key] = value
                return True
            return False

        self.current_settings[setting_key] = value
        print(f"{value} successfully added to {setting_key}")
        return True

    def _handle_list_setting(self, setting_key: str, value: str) -> bool:
        """Handle list setting updates."""
        list_handlers = {
            "directories": self._handle_directories,
            "enabled_sites": self._handle_enabled_sites,
            "default": self._handle_generic_list,
        }

        handler = list_handlers.get(setting_key, list_handlers["default"])
        return handler(setting_key, value)

    def _handle_directories(self, setting_key: str, value: str) -> bool:
        """Handle directory additions."""
        if hasattr(self, "add_directory"):
            self.add_directory(value)
            return True
        else:
            # Fallback if add_directory doesn't exist
            if os.path.exists(value):
                normalized_path = value if value.endswith(os.sep) else value + os.sep
                if normalized_path not in self.current_settings[setting_key]:
                    self.current_settings[setting_key].append(normalized_path)
                    print(f"{value} successfully added to {setting_key}")
                    return True
                else:
                    print(f"{value} already in {setting_key}")
                    return False
            else:
                print(f"Directory {value} does not exist")
                return False

    def _handle_enabled_sites(self, setting_key: str, value: str) -> bool:
        """Handle enabled sites additions."""
        if value not in self.tracker_nicknames:
            print(f"{value} is not a supported site")
            return False

        tracker = self.tracker_nicknames[value]

        # Check if API key exists
        if not self.current_settings["keys"].get(tracker):
            print(
                f"No API key for {value}. Add one using: setting-add -t {value} -s <api_key>"
            )
            return False

        # Check for duplicates
        if tracker in self.current_settings[setting_key]:
            print(f"{value} already in {setting_key}")
            return False

        self.current_settings[setting_key].append(tracker)
        print(f"{tracker} successfully added to {setting_key}")
        return True

    def _handle_generic_list(self, setting_key: str, value: str) -> bool:
        """Handle generic list additions (banned_groups, ignored_qualities, etc.)."""
        if value in self.current_settings[setting_key]:
            print(f"{value} already in {setting_key}")
            return False

        self.current_settings[setting_key].append(value)
        print(f"{value} successfully added to {setting_key}")
        return True

    def _handle_bool_setting(self, setting_key: str, value: str) -> bool:
        """Handle boolean setting updates."""
        value_lower = value.lower()

        if value_lower in ["true", "t", "1", "yes", "y"]:
            self.current_settings[setting_key] = True
            print(f"{setting_key} set to True")
            return True
        elif value_lower in ["false", "f", "0", "no", "n"]:
            self.current_settings[setting_key] = False
            print(f"{setting_key} set to False")
            return True
        else:
            print(
                f"Invalid boolean value '{value}'. Use: true/false, t/f, 1/0, yes/no, y/n"
            )
            return False

    def _handle_int_setting(self, setting_key: str, value: str) -> bool:
        """Handle integer setting updates."""
        try:
            int_value = int(value)
            self.current_settings[setting_key] = int_value
            print(f"{value} successfully added to {setting_key}")
            return True
        except ValueError:
            print(f"Invalid integer value: {value}")
            return False

    def is_upgrade(self, file, tr):
        if not file or not tr:
            print("error comparing qualities")
            return False
        if (
            file not in self.quality_hierarchy.keys()
            or tr not in self.quality_hierarchy.keys()
        ):
            return False
        if self.quality_hierarchy[file] > self.quality_hierarchy[tr]:
            return True
        else:
            return False

    def _read_json_file(self, filepath: Path) -> Optional[Dict]:
        """Read and parse JSON file."""
        try:
            with open(filepath, "r") as file:
                return json.load(file)
        except Exception as e:
            print(f"Error reading {filepath}: {e}")
            return None

    def _write_json_file(self, filepath: Path, data: Dict) -> bool:
        """Write data to JSON file."""
        try:
            filepath.parent.mkdir(exist_ok=True)
            with open(filepath, "w") as outfile:
                json.dump(data, outfile, indent=2)
            return True
        except Exception as e:
            print(f"Error writing {filepath}: {e}")
            return False

    def write_settings(self):
        """Write current settings to file."""
        return self._write_json_file(SETTINGS_FILE, self.current_settings)

    def reset_settings(self):
        """Reset settings to defaults."""
        return self._write_json_file(SETTINGS_FILE, self.default_settings)

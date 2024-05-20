import os
import json
import traceback

import requests


class Settings:
    def __init__(self):
        self.data_folder = "./data/"
        self.default_settings = {
            "directories": [],
            "tmdb_key": "",  # https://www.themoviedb.org/settings/api
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
            "search_cooldown": 5,  # In seconds. Anything less than 3 isn't recommended. 30 requests per minute is max before hit rate limits. - HDVinnie
            "min_file_size": 800,  # In MB
            "allow_dupes": True,  # If false only check for completely unique movies
            "banned_groups": [],
            "ignored_qualities": [
                "dvdrip",
                "webrip",
                "bdrip",
                "cam",
                "ts",
                "telesync",
                "hdtv",
            ],  # See patterns.py for valid options, note "bluray" get's changed to encode in scan_directories()
            "ignored_keywords": [
                "10bit",
                "10-bit",
                "DVD",
            ],  # This could be anything that would end up in the excess of parsed filename.
        }
        self.tracker_nicknames = {
            "fnp": "fearnopeer",
            "fearnopeer": "fearnopeer",
            "reelflix": "reelflix",
            "rfx": "reelflix",
            "aither": "aither",
            "aith": "aither",
            "blu": "blutopia",
            "blutopia": "blutopia",
            "lst": "lst",
            "ulcx": "upload.cx",
            "upload.cx": "upload.cx",
            "upload.cx": "ulcx",
            "onlyencodes": "oe",
            "oe": "onlyencodes",
        }

        # Basic hierarchy for qualities used to see if a file is an upgrade
        self.quality_hierarchy = {
            "webrip": 0,
            "web-dl": 1,
            "encode": 2,
            "remux": 3,
        }
        self.current_settings = None
        self.tracker_info = None

        try:
            # Creating settings.json with default settings
            if (
                not os.path.exists(f"{self.data_folder}settings.json")
                or os.path.getsize(f"{self.data_folder}settings.json") < 10
            ):
                with open(f"{self.data_folder}settings.json", "w") as outfile:
                    json.dump(self.default_settings, outfile)
            # Load settings.json
            if os.path.getsize(f"{self.data_folder}settings.json") > 10:
                with open(f"{self.data_folder}settings.json", "r") as file:
                    self.current_settings = json.load(file)
                    self.validate_directories()
            # Set the settings to our class
            if not self.current_settings:
                self.current_settings = self.default_settings
            # Load tracker_info.json used for resolution mapping
            if not self.tracker_info:
                with open("tracker_info.json", "r") as file:
                    self.tracker_info = json.load(file)
        except Exception as e:
            print("Error initializing settings: ", e)

    # Clean directories from loaded settings
    def validate_directories(self):
        try:
            directories = self.current_settings["directories"]
            directories = list(set(directories))
            # Remove trailing slashes for os.path.commonpath
            clean = [
                dir_path[:-1]
                if dir_path[-1] == "\\" or dir_path[-1] == "/"
                else dir_path
                for dir_path in directories
            ]
            clean_copy = clean
            if len(clean) > 1:
                for dir_path in clean:
                    # Check if the directory exists
                    if os.path.exists(dir_path):
                        drive, tail = os.path.splitdrive(dir_path)
                        if drive and not tail.strip("\\/"):
                            print(
                                f"{dir_path} is a root directory, removing child directories"
                            )
                            clean_copy = [
                                c for c in clean_copy if not c.startswith(drive[0])
                            ]
                            clean_copy.append(dir_path)
                            continue
                        elif dir_path in clean_copy:
                            is_subpath = False
                            child_path = None
                            parent_path = None
                            for other_dir in clean_copy:
                                if (
                                    dir_path != other_dir
                                    and os.path.commonpath([dir_path, other_dir])
                                    == dir_path
                                ):
                                    is_subpath = True
                                    child_path = (
                                        other_dir
                                        if len(other_dir) > len(dir_path)
                                        else dir_path
                                    )
                                    parent_path = (
                                        other_dir
                                        if len(other_dir) < len(dir_path)
                                        else dir_path
                                    )
                                    print(
                                        f"{child_path} is a sub-path of {parent_path}, removing"
                                    )
                                else:
                                    continue
                            if is_subpath and child_path in clean_copy:
                                clean_copy.remove(child_path)
                        else:
                            continue

                    else:
                        print(f"{dir_path} does not exist, removing")
            normalized_directories = []
            for c in clean_copy:
                if not c.endswith(os.path.sep):
                    # List comp with os.path.join() wasn't working on root directory on Windows for some reason
                    c += os.path.sep
                    normalized_directories.append(c)
                else:
                    normalized_directories.append(c)
            self.current_settings["directories"] = normalized_directories
            self.write_settings()
        except Exception as e:
            print("Error Validating Directories:", e)
            print(traceback.format_exc())

    # Add and validate new directories.
    def add_directory(self, path):
        directories = self.current_settings["directories"]
        if not os.path.exists(path):
            raise ValueError("Path doesn't exist")
        if path not in directories:
            # Add the new path to the list
            directories.append(path)
            self.validate_directories()

    def validate_tmdb(self, key):
        try:
            url = f"https://api.themoviedb.org/3/configuration?api_key={key}"
            response = requests.get(url)
            if response.status_code != 200:
                print("Invalid API Key")
                return
            else:
                self.current_settings["tmdb_key"] = key
                print("Key is valid and was added to tmdb")
        except Exception as e:
            print("Error searching api:", e)
            return

    def validate_key(self, key, target):
        api_key = None
        tracker = None
        try:
            for nn in self.tracker_nicknames:
                if target == nn:
                    tracker = self.tracker_nicknames[nn]
                    break
            if not tracker:
                print(target, " is not a supported site")
                return
            try:
                url = self.tracker_info[tracker]["url"]
                url = f"{url}api/torrents?perPage=10&api_token={key}"
                response = requests.get(url)
                # UNIT3D pushes you to the homepage if the api key is invalid
                if response.history:
                    print("Invalid API Key")
                    return
                else:
                    api_key = key
                self.current_settings["keys"][tracker] = api_key
                print("Key is valid and was added to", tracker)
            except Exception as e:
                print("Error searching api:", e)
                return

        except Exception as e:
            print("Error Validating Key:", e)

    def setting_helper(self, target):
        settings = self.current_settings
        nicknames = self.tracker_nicknames
        matching_keys = [key for key in settings.keys() if target in key]
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
        return matching_keys

    # Update a specific setting
    def update_setting(self, target, value):
        try:
            settings = self.current_settings
            nicknames = self.tracker_nicknames
            matching_key = self.setting_helper(target)
            if matching_key:
                target = matching_key  # Update target to the full key
                if target == "tmdb_key":
                    self.validate_tmdb(value)
                    settings[target] = value
                if isinstance(settings[target], str):
                    settings[target] = value
                    print(value, " Successfully added to ", target)
                elif isinstance(settings[target], list):
                    if target == "directories":
                        self.add_directory(value)
                    elif target == "enabled_sites":
                        if value in nicknames:
                            tracker = nicknames[value]
                            if not self.current_settings["keys"].get(tracker):
                                print(
                                    "There is currently no api key for",
                                    value,
                                    f"\nAdd one using setting-add -t {value} -s <api_key>",
                                )
                        else:
                            print(value, " is not a supported site")
                            return
                        if value in settings[target]:  # Don't add duplicates
                            print(value, " Already in ", target)
                            return
                        else:
                            settings[target].append(tracker)  # Add new site
                            print(tracker, "Successfully added to", target)
                    else:
                        settings[target].append(
                            value
                        )  # banned_groups, ignored_qualities, ignored_keywords these shouldn't need extra validation
                        print(value, " Successfully added to ", target)
                elif isinstance(settings[target], bool):
                    if "t" in value.lower():
                        settings[target] = True
                        print(target, " Set to True")
                    elif "f" in value.lower():
                        settings[target] = False
                        print(target, " Set to False")
                    else:
                        print(
                            "Value ", value, " Not recognized, try False, F or True, T"
                        )
                elif isinstance(settings[target], int):
                    settings[target] = int(value)
                    print(value, " Successfully added to ", target)
            # Add a new key
            elif target in nicknames:
                if not value:
                    print("No api key provided")
                else:
                    self.validate_key(value, target)
            self.current_settings = settings
            self.write_settings()
        except Exception as e:
            print("Error updating setting", e)
            print(traceback.format_exc())

    def return_setting(self, target):
        try:
            matching_key = self.setting_helper(target)
            if matching_key:
                target = matching_key  # Update target to the full key
                return self.current_settings[target]
        except Exception as e:
            print("Error returning settings: ", e)

    def remove_setting(self, target):
        try:
            matching_key = self.setting_helper(target)
            if matching_key:
                target = matching_key  # Update target to the full key
                setting = self.current_settings[target]
                if isinstance(setting, list):
                    if len(setting) > 0:
                        print(
                            "Which option would you like to remove?",
                            setting,
                            "\nType in the number of the option you want to remove:",
                            "\n0 being the first option, 1 being the second option, etc.",
                        )
                        option = int(input())
                        if option < 0 or option >= len(setting):
                            print("Option out of range")
                            return
                        removed_item = setting.pop(option)
                        # Remove trailing backslash if exists
                        removed_item = removed_item.rstrip("\\")
                        print("Removed:", removed_item)
                    else:
                        print("The setting is empty.")
                else:
                    print("The setting is not a list.")
                    print(f"Use setting-add -t {target} -s <new_value>")
                self.write_settings()
        except Exception as e:
            print("Error removing setting:", e)

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

    def write_settings(self):
        try:
            with open(f"{self.data_folder}settings.json", "w") as outfile:
                json.dump(self.current_settings, outfile)
        except Exception as e:
            print("Error writing settings: ", e)

    def reset_settings(self):
        try:
            with open(f"{self.data_folder}settings.json", "w") as outfile:
                json.dump(self.default_settings, outfile)
        except Exception as e:
            print("Error resetting settings: ", e)

import os
import json

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
                "10bit"
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

    # Make sure directories exist and have trailing slashes
    def validate_directories(self):
        try:
            directories = self.current_settings["directories"]
            clean = []
            for dir in directories:
                if os.path.exists(dir):
                    trailing = os.path.join(dir, "")
                    clean.append(trailing)
                else:
                    print(dir, "Does not exist, removing")
            clean = list(set(clean))
            self.current_settings["directories"] = clean
            self.write_settings()
        except Exception as e:
            print("Error Validating Directories:", e)
    
    def validate_tmdb(self, key):
        try:
            url = f"https://api.themoviedb.org/3/configuration?api_key={key}"
            response = requests.get(url)
            if response.history:
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


    # Update a specific setting
    def update_setting(self, target, value):
        try:
            settings = self.current_settings
            nicknames = self.tracker_nicknames
            matching_keys = [key for key in settings.keys() if target in key]
            if len(matching_keys) == 1:
                target = matching_keys[0]  # Update target to the full key
                if target == "tmdb_key":
                    self.validate_tmdb(value)
                    settings[target] = value
                    return
                if isinstance(settings[target], str):
                    settings[target] = value
                    print(value, " Successfully added to ", target)
                elif isinstance(settings[target], list):
                    if target == "directories":
                        path = os.path.join(value, "") # Ensure trailing slashes
                        if os.path.exists(path) and path not in settings[target]:
                            settings[target].append(path) # Add new directory
                            print(value, " Successfully added to ", target)
                        elif path in settings[target]: # Don't add duplicates
                            print(value, " Already in ", target)
                        else:
                            print("Path not found")
                    elif target == "enabled_sites":
                        if value in nicknames:
                            tracker = nicknames[value]
                            if not self.current_settings["keys"].get(tracker):
                                print("There is currently no api key for", value, "\nAdd one using setting-add -t <site> -s <api_key>", f"\ne.g. setting-add -t {value} -s <api_key>")
                        else:
                            print(value, " is not a supported site") 
                            return
                        if value in settings[target]: # Don't add duplicates
                            print(value, " Already in ", target)
                            return
                        else:
                            settings[target].append(tracker) # Add new site
                            print(tracker, "Successfully added to", target)
                    else:
                        settings[target].append(value) # banned_groups, ignored_qualities, ignored_keywords these shouldn't need extra validation
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
            elif len(matching_keys) > 1:
                print("Multiple settings match the provided substring. Please provide a more specific target.")
                print(settings.keys())
                print("Unique substrings accepted: dir, tmdb, sites, gg, search, size, dupes, banned, qual, keywords")
                print("If you're trying to add a tracker key, you can use setting-add -t <site> -s <api_key>")
                print("Accepted sites: ", nicknames.keys())
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
            self.current_settings = settings
            self.write_settings()
        except Exception as e:
            print("Error updating setting", e)

    def return_setting(self, target):
        try:
            if target in self.current_settings:
                return self.current_settings[target]
            else:
                return (target, " Not found in current settings.")
        except Exception as e:
            print("Error returning settings: ", e)
    def remove_setting(self, target):
        try:
            if target in self.current_settings:
                setting = self.current_settings[target]
                if isinstance(setting, list):
                    if len(setting) > 0:
                        print(
                            "Which option would you like to remove?",
                            setting,
                            "\nType in the number of the option you want to remove:",
                            "\n0 being the first option, 1 being the second option, etc."
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
                self.write_settings()
        except Exception as e:
            print("Error removing setting:", e)

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

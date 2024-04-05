#!/usr/bin/env python3
import os
import re
import csv
import glob
import sys
import traceback
from PTN.parse import (
    PTN,
)  # For parsing filenames pip install parse-torrent-name was not working for me
import json
import requests
from thefuzz import fuzz  # For matching titles with tmdb
import time
import math
import argparse
from mediainfo import get_media_info, format_media_info
from settings import Settings


class UploadChecker:
    def __init__(self):
        self.settings = Settings()
        self.update_settings()
        self.tracker_info = self.settings.tracker_info
        self.output_folder = "./outputs/"
        self.data_folder = "./data/"
        self.scan_data = {}
        self.search_data = {}
        self.term_size = os.get_terminal_size()
        self.extract_filename = re.compile(r"^.*[\\\/](.*)")

        # Initialize search data for enabled sites
        try:
            for tracker in self.enabled_sites:
                self.search_data[tracker] = {
                    "safe": {},
                    "risky": {},
                    "danger": {},
                }
        except Exception as e:
            print("Error loading enabled sites ", e)

        # Create database files if they don't exist
        try:
            if not os.path.exists(f"{self.data_folder}database.json"):
                with open(f"{self.data_folder}database.json", "w") as outfile:
                    json.dump({}, outfile)
            if not os.path.exists(f"{self.data_folder}search_data.json"):
                with open(f"{self.data_folder}search_data.json", "w") as outfile:
                    json.dump(self.search_data, outfile)
            self.database_location = f"{self.data_folder}database.json"
            self.search_data_location = f"{self.data_folder}search_data.json"
        except Exception as e:
            print("Error initializing json files: ", e)

        # Update our class data with data from json files
        try:
            if os.path.getsize(self.database_location) > 10:
                with open(self.database_location, "r") as file:
                    self.scan_data = json.load(file)
            if os.path.getsize(self.search_data_location) > 10:
                with open(self.search_data_location, "r") as file:
                    self.search_data = json.load(file)
        except Exception as e:
            print("Error loading json files: ", e)

    # Scan given directories
    def scan_directories(self, verbose=False):
        try:
            print("Scanning Directories")
            if not self.directories:
                print("Please add a directory")
                print("setting-add -t dir -s <dir>")
                return False
            # loop through provided directories
            for dir in self.directories:
                # check if the directory has previously scanned data
                if dir in self.scan_data:
                    dir_data = self.scan_data[dir]
                else:
                    dir_data = {}
                # get all .mkv files in current directory
                files = glob.glob(f"{dir}**\\*.mkv", recursive=True) or glob.glob(
                    f"{dir}**/*.mkv", recursive=True
                )
                for f in files:
                    if verbose:
                        print("=" * self.term_size.columns)
                        print(f"Scanning: {f}")
                    file_location = f
                    file_name = self.extract_filename.match(f).group(1)
                    bytes = os.path.getsize(f)
                    file_size = self.convert_size(bytes)
                    if verbose:
                        print("File size: ", file_size)
                    # check if file exists in our database already
                    if file_name in dir_data:
                        if verbose:
                            print(file_name, "Already exists in database.")
                        continue
                    parsed = parse_file(file_name)
                    group = (
                        re.sub(r"(\..*)", "", parsed["group"])
                        if "group" in parsed
                        else None
                    )
                    banned = False

                    codec = parsed["codec"] if "codec" in parsed else None
                    year = str(parsed["year"]).strip() if "year" in parsed else ""
                    title = parsed["title"].strip()
                    year_in_title = re.search(r"\d{4}", title)
                    # Extract the year from the title if PTN didn't work properly hopefully this doesn't ruin movies with a year in the title like 2001 a space...
                    # but I noticed a lot of failed parses in my testing.
                    if year_in_title and not year:
                        year = year_in_title.group().strip()
                        # Only remove year from title if parser didn't add year. Hopefully this helps with the above possible problem
                        title = re.sub(r"[\d]{4}", "", title).strip()
                        if verbose:
                            print("Year manually added from title: ", title, year)
                    quality = (
                        re.sub(r"[^a-zA-Z]", "", parsed["quality"]).strip()
                        if "quality" in parsed
                        else None
                    )
                    quality = quality.lower() if quality else None
                    if quality == "bluray":
                        quality = "encode"
                    elif quality == "web":
                        quality = "webrip"
                    resolution = (
                        parsed["resolution"].strip() if "resolution" in parsed else None
                    )
                    # Set these to banned so they're saved in our database and we don't re-scan every time.
                    if group in self.banned_groups:
                        if verbose:
                            print(group, "Is flagged for banning. Banned")
                        banned = True
                    elif bytes < (self.minimum_size * 1024) * 1024:
                        if verbose:
                            print(file_size, "Is below accepted size. Banned")
                        banned = True
                    elif "season" in parsed or "episode" in parsed:
                        if verbose:
                            print(file_name, "Is flagged as tv. Banned")
                        banned = True
                    elif quality and (quality in self.ignore_qualities):
                        if verbose:
                            print(quality, "Is flagged for banning. Banned")
                        banned = True
                    # Ban x265 encodes
                    elif (
                        resolution
                        and codec
                        and ("265" in codec)
                        and ("2160" not in resolution)
                        and (quality == "encode")
                    ):
                        if verbose:
                            print(
                                resolution, "@", codec, "Is flagged for banning. Banned"
                            )
                        banned = True
                    if "excess" in parsed:
                        for kw in self.ignore_keywords:
                            if kw.lower() in (
                                excess.lower() for excess in parsed["excess"]
                            ):
                                if verbose:
                                    print(
                                        "Keyword ", kw, "Is flagged for banning. Banned"
                                    )
                                banned = True
                                break
                    dir_data[file_name] = {
                        "file_location": file_location,
                        "file_name": file_name,
                        "file_size": file_size,
                        "title": title,
                        "quality": quality,
                        "resolution": resolution,
                        "year": year,
                        "tmdb": None,
                        "banned": banned,
                    }
                    if verbose and not banned:
                        print(dir_data[file_name])
                self.scan_data[dir] = dir_data
                self.save_database()
        except Exception as e:
            print("Error scanning directories: ", e)

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
                    year_url = f"&year={year}" if year else ""
                    # This seems possibly problematic
                    clean_title = re.sub(r"[^0-9a-zA-Z]", " ", title)
                    query = clean_title.replace(" ", "%20")
                    try:
                        url = f"https://api.themoviedb.org/3/search/movie?query={query}&include_adult=false&language=en-US&page=1&api_key={self.tmdb_key}{year_url}"
                        res = requests.get(url)
                        data = json.loads(res.content)
                        results = data["results"] if "results" in data else None
                        # So we don't keep searching queries with no results
                        if not results:
                            if verbose:
                                print("No results, Banning.")
                            value["banned"] = True
                            self.save_database()
                            continue
                        for r in results:
                            # This definitely isn't a great solution but I was noticing improper matches. ex: Mother 2009
                            if "vote_count" in r and (
                                r["vote_count"] == 0 or r["vote_count"] <= 5
                            ):
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
        except Exception as e:
            print("Error searching TMDB: ", e)

    # Search trackers
    def search_trackers(self, verbose=False):
        try:
            print("Searching trackers")
            for t in self.enabled_sites:
                api_key = self.current_settings["keys"][t]
                if not api_key:
                    print(f"No API key for {t} found.")
                    print(
                        "If you want to use this tracker, add an API key to the settings."
                    )
                    if not input("Continue? [y/n] ").lower().startswith("y"):
                        return False

            for dir in self.scan_data:
                for key, value in self.scan_data[dir].items():
                    # Skip unnecessary searches.
                    if value["banned"]:
                        continue
                    if value["tmdb"] is None:
                        continue
                    print("=" * self.term_size.columns)
                    print(f"Searching Trackers for {value['title']}")
                    if verbose:
                        print(f"Filename: {value['file_name']}")
                    tmdb = value["tmdb"]
                    quality = value["quality"] if value["quality"] else None
                    resolution = value["resolution"] if value["resolution"] else None
                    if "trackers" not in value:
                        value["trackers"] = {}
                    try:
                        # Query each trackers api
                        for tracker in self.enabled_sites:
                            try:
                                # The file already contains the results from a given tracker. Skip it.
                                if tracker in value["trackers"]:
                                    if verbose:
                                        print(
                                            f"{self.output_folder}{tracker} already searched. For {value['title']} Skipping."
                                        )
                                    continue
                                url = self.tracker_info[tracker]["url"]
                                key = self.current_settings["keys"][tracker]
                                if not key:
                                    print(f"No API key for {tracker} found. Skipping.")
                                    continue
                                url = f"{url}api/torrents/filter?tmdbId={tmdb}&categories[]=1&api_token={key}"
                                response = requests.get(url)
                                res_data = json.loads(response.content)
                                results = res_data["data"] if res_data["data"] else None
                                tracker_message = None
                                # If there are any results and user has allow_dupes set to False, then banning.
                                if results and not self.allow_dupes:
                                    print(
                                        "Duplicate results detected and allow_dupes is set to False. Banning."
                                    )
                                    value["trackers"][tracker] = True
                                    continue
                                if results:
                                    loop_results = {}
                                    for i, result in enumerate(results):
                                        dupe_res = False
                                        dupe_quality = False
                                        # Get info from tracker.
                                        info = result["attributes"]
                                        tracker_resolution = info["resolution"]
                                        tracker_quality = re.sub(
                                            r"[^a-zA-Z]",
                                            "",
                                            info["type"],
                                        ).strip()
                                        # Store resolutions for comparison
                                        # Remove all non-numeric characters for easier comparison (e.g. 1080p from file incorrectly named.)
                                        clean_tracker_resolution = "".join(
                                            re.findall(r"\d+", tracker_resolution)
                                        )
                                        clean_file_resolution = (
                                            "".join(re.findall(r"\d+", resolution))
                                            if resolution
                                            else None
                                        )
                                        # The resolutions are the same
                                        if (
                                            clean_file_resolution
                                            and clean_file_resolution
                                            == clean_tracker_resolution
                                        ):
                                            dupe_res = True

                                        if (
                                            quality
                                            and tracker_quality.lower()
                                            == quality.lower()
                                        ):
                                            dupe_quality = True
                                        # The tracker has a similar release already
                                        # We can break the loop.
                                        if dupe_res and dupe_quality:
                                            tracker_message = True
                                            value["trackers"][tracker] = tracker_message
                                            break
                                        # The tracker has a release with the same resolution, but couldn't determine input source quality.
                                        elif (dupe_res and not quality) or (
                                            quality and dupe_quality and not resolution
                                        ):
                                            # This could probably be set to True, but I'm not sure.
                                            tracker_message = f"Source was found on {tracker}, but couldn't get enough info from filename. Manual search required."
                                            value["trackers"][tracker] = tracker_message
                                            break
                                        elif dupe_res and quality:
                                            loop_message = "Resolution match, but could be a new quality. Manual search recommended."
                                            loop_results[i] = loop_message
                                    else:
                                        if loop_results:
                                            tracker_message = f"Resolution found on {tracker}, but could be a new quality. Manual search recommended."
                                            value["trackers"][tracker] = tracker_message
                                        # No results found, not on tracker.
                                        else:
                                            tracker_message = f"Possible new release. {quality if quality else ''} {resolution if resolution else ''}"
                                            value["trackers"][tracker] = tracker_message
                                else:
                                    # No results found, not on tracker.
                                    tracker_message = False
                                    value["trackers"][tracker] = tracker_message
                                if verbose:
                                    if tracker_message is True:
                                        print(f"Already on {tracker}")
                                    elif tracker_message is False:
                                        print(f"Not on {tracker}")
                                    else:
                                        print(tracker_message)
                            except Exception as e:
                                print(
                                    f"Something went wrong searching {tracker} for {value['title']} ",
                                    e,
                                )
                        print("Waiting for cooldown...", self.cooldown, "seconds")
                        time.sleep(self.cooldown)
                    except Exception as e:
                        print(
                            f"Something went wrong searching trackers for {value['title']} ",
                            e,
                        )
                    self.save_database()
            self.save_database()
        except Exception as e:
            print("Error searching blu: ", e)

    # Create search_data.json
    def create_search_data(self, mediainfo=True):
        try:
            print("Creating search data.")
            for dir in self.scan_data:
                for key, value in self.scan_data[dir].items():
                    if value["banned"]:
                        continue
                    if "trackers" not in value:
                        continue
                    media_info = None
                    # Loop through each tracker and get tracker specific info.
                    try:
                        for tracker, info in value["trackers"].items():
                            title = value["title"]
                            year = value["year"]
                            file_location = value["file_location"]
                            file_size = value["file_size"]
                            quality = value["quality"]
                            resolution = value["resolution"]
                            tmdb = value["tmdb"]
                            tmdb_year = value["tmdb_year"]
                            extra_info = (
                                "TMDB Release year and given year are different this might mean improper match manual search required"
                                if (year != tmdb_year)
                                else ""
                            )
                            message = None
                            if isinstance(info, bool):
                                if info is False:
                                    message = f"Not on {tracker}"
                                elif info is True:
                                    message = "Dupe!"
                            else:
                                message = info
                            if "Dupe!" in message:
                                continue
                            # Get media info if mediainfo is True and not previously scanned.
                            if mediainfo is True and not media_info:
                                audio_language, subtitles, video_info, audio_info = (
                                    get_media_info(file_location)
                                )
                                if "en" not in audio_language and "en" not in subtitles:
                                    extra_info += (
                                        " No English subtitles found in media info"
                                    )
                                media_info = {
                                    "audio_language(s)": audio_language,
                                    "subtitle(s)": subtitles,
                                    "video_info": video_info,
                                    "audio_info": audio_info,
                                }
                            elif mediainfo is True and media_info:
                                audio_language = media_info["audio_language(s)"]
                                subtitles = media_info["subtitle(s)"]
                                if "en" not in audio_language and "en" not in subtitles:
                                    extra_info += (
                                        " No English subtitles found in media info"
                                    )
                            # Create dictionary for each tracker.
                            tracker_info = {
                                "file_location": file_location,
                                "year": year,
                                "quality": quality,
                                "resolution": resolution,
                                "tmdb": tmdb,
                                "tmdb_year": tmdb_year,
                                "message": message.strip(),
                                "file_size": file_size,
                                "extra_info": extra_info.strip(),
                                "media_info": media_info,
                            }
                            # Add to self.search_data. In the appropriate danger/safe/risky/etc. section.
                            # Matched years
                            if tmdb_year == year:
                                # No English subtitles or audio
                                if "English" in extra_info:
                                    self.search_data[tracker]["danger"][title] = (
                                        tracker_info
                                    )
                                    continue
                                # Not on tracker
                                if isinstance(info, bool) and info is False:
                                    self.search_data[tracker]["safe"][title] = (
                                        tracker_info
                                    )
                                    continue
                                # Not on tracker at a given resolution or quality.
                                if "Possible" in info:
                                    self.search_data[tracker]["safe"][title] = (
                                        tracker_info
                                    )
                                    continue
                                # On tracker but either couldn't get resolution or quality from filename.
                                if "required" in info:
                                    self.search_data[tracker]["danger"][title] = (
                                        tracker_info
                                    )
                                    continue
                                # On tracker at given resolution but quality might be new
                                if "recommended" in info:
                                    self.search_data[tracker]["risky"][title] = (
                                        tracker_info
                                    )
                                    continue
                                # Probably unnecessary
                                else:
                                    self.search_data[tracker]["danger"][title] = (
                                        tracker_info
                                    )
                                    continue
                            # TMDB + Filename year mismatch or simply no year in filename.
                            else:  
                                self.search_data[tracker]["danger"][title] = (
                                    tracker_info
                                )
                    except Exception as e:
                        print("Error creating search_data.json:", e)
            self.save_search_data()
        except Exception as e:
            print("Error creating search_data.json", e)

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
            print("Error writing to blu_data.json: ", e)

    # Empty json files
    def clear_data(self):
        try:
            with open(self.search_data_location, "w") as of:
                json.dump({}, of)
            with open(self.database_location, "w") as of:
                json.dump({}, of)
            print("Data cleared!")
        except Exception as e:
            print("Error clearing json data: ", e)

    # Run main functions
    def run_all(self, mediainfo=True, verbose=False):
        check_1 = self.scan_directories(verbose)
        if check_1 is False:
            return
        check_2 = self.get_tmdb(verbose)

        if check_2 is False:
            return

        self.search_trackers(verbose)
        self.create_search_data(mediainfo)
        self.export_gg()
        self.export_txt()
        self.export_csv()

    # Export gg-bot auto_upload commands.
    def export_gg(self):
        # For gg-bot -t flag
        TRACKER_MAP = {
            "aither": "ATH",
            "blutopia": "BLU",
            "fearnopeer": "FNP",
            "reelflix": "RFX",
        }
        try:
            for tracker, data in self.search_data.items():
                if data["safe"]:
                    with open(f"{self.output_folder}{tracker}_gg.txt", "w") as f:
                        f.write("")
                    platform = sys.platform
                    py_version = "python3" if "linux" in platform else "py"
                    tracker_flag = TRACKER_MAP[tracker]

                    for file, value in data["safe"].items():
                        line = (
                            py_version
                            + " "
                            + f"{self.gg_path}auto_upload.py "
                            + "-p "
                            + value["file_location"]
                            + " -t "
                            + tracker_flag
                        )
                        with open(
                            f"{self.output_folder}{tracker}_gg.txt", "a"
                        ) as append:
                            append.write(line + "\n")

                print(
                    "Exported gg-bot auto_upload commands.",
                    f"{self.output_folder}{tracker}_gg.txt",
                )

        except Exception as e:
            raise e

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
                        url_query = title.replace(" ", "%20")
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
                            audio_language, audio_info, subtitles, video_info = (
                                format_media_info(media_info)
                            )
                            clean_mi = f"""
            Language(s): {audio_language}
            Subtitle(s): {subtitles}
            Audio Info: {audio_info}
            Video Info: {video_info}
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
                                url_query = title.replace(" ", "%20")
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
                                        audio_info,
                                        subtitles,
                                        video_info,
                                    ) = format_media_info(media_info)
                                    clean_mi = f"Language(s): {audio_language}, Subtitle(s): {subtitles}, Audio Info: {audio_info}, Video Info: {video_info}"

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

    # Settings functions
    def update_settings(self):
        self.current_settings = self.settings.current_settings
        self.directories = self.current_settings["directories"]
        self.tmdb_key = self.current_settings["tmdb_key"]
        self.enabled_sites = self.current_settings["enabled_sites"]
        self.cooldown = self.current_settings["search_cooldown"]
        self.minimum_size = self.current_settings["min_file_size"]
        self.allow_dupes = self.current_settings["allow_dupes"]
        self.banned_groups = self.current_settings["banned_groups"]
        self.ignore_qualities = self.current_settings["ignored_qualities"]
        self.ignore_keywords = self.current_settings["ignored_keywords"]
        self.gg_path = self.current_settings["gg_path"]

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


ptn = PTN()


def parse_file(name):
    return ptn.parse(name)


ch = UploadChecker()
parser = argparse.ArgumentParser()


FUNCTION_MAP = {
    "scan": ch.scan_directories,
    "tmdb": ch.get_tmdb,
    "search": ch.search_trackers,
    "save": ch.create_search_data,
    "run-all": ch.run_all,
    "clear-data": ch.clear_data,
    "setting-add": ch.update_setting,
    "setting-rm": ch.remove_setting,
    "setting": ch.get_setting,
    "txt": ch.export_txt,
    "csv": ch.export_csv,
    "gg": ch.export_gg,
}


parser.add_argument("command", choices=FUNCTION_MAP.keys())

parser.add_argument(
    "-m",
    "--mediainfo",
    action="store_false",
    help="Turn off mediainfo scanning, only accessible with the [save] command",
    default=True,
)
parser.add_argument(
    "--target",
    "-t",
    help="Specify the target setting to update."
    "\nValid targets: directories, tmdb_key, enabled_sites, gg_path, search_cooldown, min_file_size, allow_dupes, banned_groups, ignored_qualities, ignored_keywords"
    "\nYou can also use setting-add to add api keys: -t aith, blu, fnp, rfx. followed by -s <key>",
)
parser.add_argument("--set", "-s", help="Specify the new value for the target setting")

parser.add_argument(
    "--verbose",
    "-v",
    action="store_true",
    help="Enable verbose output. Only works with [scan, tmdb, search, and run-all]",
    default=False,
)

args = parser.parse_args()

# Get the appropriate function based on the command
func = FUNCTION_MAP[args.command]
func_args = {}

# Check if the function accepts mediainfo argument, and if yes, include it
if "mediainfo" in ch.create_search_data.__code__.co_varnames:
    if args.command in {"run-all", "save"}:
        func_args["mediainfo"] = args.mediainfo

# Include other specific arguments based on the command
if args.command == "setting" or args.command == "setting-rm":
    func_args["target"] = args.target
if args.command == "setting-add":
    func_args["value"] = args.set
    func_args["target"] = args.target
if args.command in {"scan", "tmdb", "search", "run-all"}:
    func_args["verbose"] = args.verbose

# Call the function with appropriate arguments
func(**func_args)

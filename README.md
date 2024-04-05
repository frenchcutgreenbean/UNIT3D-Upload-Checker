# Features

- Scan directories for movies (.mkv)
- Parse filenames then search on TMDB
- Use TMDB id + resolution (if found) to search Blutopia for unique movies
- Ability to ignore groups, qualities, and other keywords.
- Scan the file with mediainfo to ensure either English audio or English subtitles.
- Export possible uploads to gg-bot commands and .txt or csv files

## Sites Supported

- Aither
- Blutopia
- Fearnopeer
- Reelflix

But any UNIT3D trackers can be supported by adding the necessary info.

## Setup

```sh
git clone https://github.com/frenchcutgreenbean/UNIT3D-Upload-Checker.git
```

```sh
cd UNIT3D-Upload-Checker
```

```sh
pip install -r requirements.txt
```

```sh
chmod +x check.py
```

## Example Outputs

### CSV

![csv output](https://i.ibb.co/SmkvfV1/2024-04-03-19-38-21.png)

## Usage

### Edit settings

#### Settings needed to work

"directories"
format ["C:\\", "D:\\"] or linux ["/home/"]
CLI Command:

```sh
./check.py setting-add --target dir --set /home/movies/
```

windows

```sh
py .\check.py setting-add --t dir -s C:\Users\user\movies
```

-t and -s accepted

Add supported tracker key: (aith, blu, fnp, rfx)

```sh
./check.py setting-add -t blu -s asdasdasd
```

Enable sites:

```sh
./check.py setting-add -t sites -s blu
```

"tmdb_key"
Your TMDB api key.

```sh
./check.py setting-add -t tmdb -s asdasdasd
```

You can target and edit most settings following the same structure. Or you can manually edit in settings.json

## Accepted commands

"run-all" Scans, Searches and exports possible uploads

"clear-data" Empties database.json and blu_data.json

"add-setting" Adds or edits a setting. --target setting_name --set setting_value

"setting" Prints a given settings value. --target setting_name

### These should be run in order. They need data from previous functions

"scan" Scans directories in main.py

"tmdb" Searches TMDB for found movies  

"search" Searches trackers by TMDB id

"save" Creates search_data.json

"gg" Creates gg auto_upload commands txt file

"txt" Creates txt file with useful information for possible uploads

"csv" Creates CSV file with useful information for possible uploads

Accepted flags:

-m or --mediainfo This works only with the blu and run-all command it will disable scanning with mediainfo.
-v or --verbose This only works for scanning and searching for now.

## FAQ

Q: What puts a movie in "safe"?

A: If the file does not exist on the tracker, or the resolution is new.

Q: What puts a movie in "risky"?

A: The movie exists on the tracker, but the quality is new. e.g. web-dl, remux, etc.

Q: What puts a movie in "danger"?

A: There are multiple reasons why the movie gets put in "danger".

1: The year from the filename is different to the one matched on TMDB.

2: Mediainfo couldn't find English language subtitles or audio.

3: The movie exists on the tracker, but quality couldn't be extracted from filename.

Q: How can I add support for different UNIT3D tracker?

A: First you need to edit tracker_info.json. Then, append the relevant details in settings.py. self.tracker_nicknames & self.default_settings["keys"]

Q: Why is tracker x not supported?

A: I only added trackers I am on. Pull requests are welcomed!

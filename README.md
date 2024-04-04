# Features

- Scan directories for movies (.mkv)
- Parse filenames then search on TMDB
- Use TMDB id + resolution (if found) to search Blutopia for unique movies
- Ability to ignore groups, qualities, and other keywords.
- Scan the file with mediainfo to ensure either English audio or English subtitles.
- Export possible uploads to gg-bot commands and .txt or csv files

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

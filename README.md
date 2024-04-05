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

### TXT

<https://github.com/frenchcutgreenbean/UNIT3D-Upload-Checker/blob/main/manual_txt_example.txt>

### GG

<https://github.com/frenchcutgreenbean/UNIT3D-Upload-Checker/blob/main/manual_bot_example.txt>

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

### Settings specific

All settings can be targeted by unique substrings. For example "dir" for "directories" and "sites" for "enabled_sites".

"setting" Prints a given settings value.

```sh
./check.py setting -t dir
['/home/user/media/'] 
```

"setting-add" Adds or edits a setting.

```sh
./check.py setting-add -t dir -s /home/user/movies
/home/user/movies/  Successfully added to  directories
```

"setting-rm" Only works on lists, returns prompt to remove specific value.

```sh
./check.py setting-rm -t dir
Which option would you like to remove? ['/home/user/media/', '/home/user/movies/']
Type in the number of the option you want to remove:
0 being the first option, 1 being the second option, etc.
0
Removed: /home/user/media/
```

### These should be run in order. They need data from previous functions

| command | function | flags |
|---------|----------|-------|
| scan | Scans directories in main.py| -v |
| tmdb| Searches TMDB for found movies| -v |
| search | Searches trackers by TMDB id|-v |
| save | Creates search_data.json| -m |
| gg | Creates gg auto_upload commands txt file| |
| txt | Creates txt file with useful information | |
| csv | Creates CSV file with useful information | |

-m or --mediainfo This will disable scanning with mediainfo. *Not recommended*.

-v or --verbose Prints more stuffs.

## FAQ

Q: What puts a movie in "safe"?

- A: If the file does not exist on the tracker, or the resolution is new.

Q: What puts a movie in "risky"?

- A: The movie exists on the tracker, but the quality is new. e.g. web-dl, remux, etc.

Q: What puts a movie in "danger"?

- A: There are multiple reasons why the movie gets put in "danger".

- 1: The year from the filename is different to the one matched on TMDB.

- 2: Mediainfo couldn't find English language subtitles or audio.

- 3: The movie exists on the tracker, but quality couldn't be extracted from filename.

Q: How can I add support for different UNIT3D tracker?

- A: First you need to edit tracker_info.json. Then, append the relevant details in settings.py. self.tracker_nicknames & self.default_settings["keys"]

Q: Why is tracker x not supported?

- A: I only added trackers I am on. Pull requests are welcomed!

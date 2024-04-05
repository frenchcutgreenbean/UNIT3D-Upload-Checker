# Features

- Scan directories for movies (.mkv only)
- Parse filenames then search on TMDB
- Use TMDB id + resolution (if found) to search trackers for unique movies
- Ability to ignore groups, qualities, and other keywords.
- Scan the file with mediainfo to ensure either English audio or English subtitles.
- Export possible uploads to gg-bot commands and .txt or .csv files

## Sites Supported

- Aither
- Blutopia
- Fearnopeer
- Reelflix

Any UNIT3D trackers can be supported by adding the necessary info.

## Quick Start

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

### Add Required Settings

directories

```sh
./check.py setting-add --target dir --set /home/movies/
```

-t and -s accepted

Add tracker key or keys: (aith, blu, fnp, rfx)

```sh
./check.py setting-add -t blu -s <api_key>
```

Enable sites:

```sh
./check.py setting-add -t sites -s blu
```

Your TMDB api key.

```sh
./check.py setting-add -t tmdb -s <api_key>
```

run all

```sh
./check.py run-all -v
```

## Example Outputs

### CSV

![csv output](https://i.ibb.co/SmkvfV1/2024-04-03-19-38-21.png)

### TXT

<https://github.com/frenchcutgreenbean/UNIT3D-Upload-Checker/blob/main/manual_txt_example.txt>

### GG

<https://github.com/frenchcutgreenbean/UNIT3D-Upload-Checker/blob/main/manual_bot_example.txt>

## Accepted commands

| Command | Description| Flags |
|---------|------------|-------|
| run-all | Runs all scanning, searching, and exporting functions. | -v -m |
| setting | Prints a given setting's value.| |
| setting-add | Adds or edits a setting. | |
| setting-rm | Only works on lists, returns prompt to remove specific value. | |

*-v and -m only affect certain functions; see below.*

### Examples

```sh
./check.py setting -t dir
['/home/user/media/'] 
```

```sh
./check.py setting-add -t dir -s /home/user/movies
/home/user/movies/  Successfully added to  directories
```

```sh
./check.py setting-rm -t dir
Which option would you like to remove? ['/home/user/media/', '/home/user/movies/']
Type in the number of the option you want to remove:
0 being the first option, 1 being the second option, etc.
0
Removed: /home/user/media/
```

### Manually run the commands in run-all

| Command | Description | Flags |
|---------|----------|-------|
| scan | Scans directories in main.py| -v |
| tmdb | Searches TMDB for found movies| -v |
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

Q: Why is tracker x not supported?

- A: I only added trackers I am on. Pull requests are welcomed!

Q: How can I add support for different UNIT3D trackers?

- A: First you need to edit tracker_info.json. Then, append the relevant details in settings.py. self.tracker_nicknames & self.default_settings["keys"]

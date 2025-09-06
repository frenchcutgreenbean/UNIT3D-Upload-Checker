# UNIT3D Upload Checker

A command-line tool to scan directories for movies and check for duplicates across UNIT3D trackers.

## Features

- Scan directories for movies (.mkv only)
- Parse filenames then search on TMDB
- Use TMDB id + resolution (if found) to search trackers for unique movies
- Ability to ignore groups, qualities, and other keywords
- Scan files with mediainfo to ensure either English audio or English subtitles
- Export possible uploads to gg-bot commands and .txt or .csv files
- Store information for fast subsequent searches.

## Sites Supported

- Aither
- BeyondHD
- Blutopia
- FearNoPeer
- LST
- OnlyEncodes
- ReelFliX
- Upload.cx

Any UNIT3D trackers can be supported by adding the necessary info.

## Warning

I am not responsible for your accounts on any trackers. You should always verify the files yourself looking in the {site}_uploads.txt.

It includes valuable information about your files, and links to the tracker for you to verify the results.

## Quick Start

```sh
git clone https://github.com/frenchcutgreenbean/UNIT3D-Upload-Checker.git
cd UNIT3D-Upload-Checker

# Create and activate a virtual environment (optional)
python -m venv venv
source venv/bin/activate      # On Linux/macOS
venv\Scripts\activate         # On Windows

pip install -r requirements.txt
```

### Add Required Settings

Run init
```sh
python uploadchecker.py init
```
Now you can edit settings.json manually or continue using CLI:

Add directories to scan:
```sh
python uploadchecker.py add dir /home/movies/
```

Add tracker API keys:
```sh
python uploadchecker.py add blu <api_key>
python uploadchecker.py add aith <api_key>
python uploadchecker.py add fnp <api_key>
python uploadchecker.py add rfx <api_key>
```

Enable sites:
```sh
python uploadchecker.py add enabled_sites blu
python uploadchecker.py add enabled_sites aith
```

Add your TMDB API key:
```sh
python uploadchecker.py add tmdb_key <api_key>
```

Run the complete workflow:
```sh
python uploadchecker.py run-all -v
```

## Commands

### Workflow Commands

| Command    | Description                                               | Flags                |
|------------|-----------------------------------------------------------|----------------------|
| `run-all`  | Run complete workflow (scan → tmdb → search → save → export) | `-v`, `--no-mediainfo`, `--log` |
| `scan`     | Scan directories for media files                          | `-v`, `--log`        |
| `tmdb`     | Search TMDB for movie information                         | `-v`, `--log`        |
| `search`   | Search trackers for duplicates                            | `-v`, `--log`        |
| `save`     | Create search data from results                           | `--no-mediainfo`, `--log` |

### Settings Commands

| Command        | Description                | Examples                                      |
|----------------|---------------------------|-----------------------------------------------|
| `setting`      | View current settings      | `python uploadchecker.py setting directories` |
| `add`  | Add or update a setting    | `python uploadchecker.py add tmdb_key YOUR_KEY` |
| `rm`   | Remove a setting value     | `python uploadchecker.py rm directories` |

### Logging

Most commands support the `--log` flag to enable file logging. When enabled:
- Log files are saved to the `logs/` directory with timestamps
- Log level is set to DEBUG when used with the `-v` flag
- Logs include colored output in the console and detailed info in the file
- Log files use the format `uploadchecker_YYYYMMDD_HHMMSS.log`

### Export Commands

| Command | Description                    | Options           |
|---------|--------------------------------|-------------------|
| `txt`   | Export results to text format  | `--log`           |
| `csv`   | Export results to CSV format   | `--log`           |
| `gg`    | Export GG bot commands         | `--log`           |
| `ua`    | Export upload-assistant commands | `--log`         |

### Utility Commands

| Command      | Description                                 |
|--------------|---------------------------------------------|
| `clear-data` | Clear all stored scan and search data        |

## Command Line Examples

### Enabling Logging

```bash
# Run complete workflow with verbose output and file logging
python uploadchecker.py run-all -v --log

# Export to TXT with logging
python uploadchecker.py txt --log
```

### Settings Management

```sh
# View specific setting
python uploadchecker.py setting directories

# Add a directory
python uploadchecker.py add directories /home/user/movies/

# Add API key
python uploadchecker.py add blu your_api_key_here

# Remove a directory
# Returns options to remove specific one
python uploadchecker.py rm directories

# View available commands
python uploadchecker.py --help

# Get help for specific command
python uploadchecker.py scan --help
```

### Workflow Examples
```sh
# Run complete workflow with verbose output
python uploadchecker.py run-all -v

# Run individual steps
python uploadchecker.py scan -v
python uploadchecker.py tmdb -v
python uploadchecker.py search -v
python uploadchecker.py save

# Export results
python uploadchecker.py gg
python uploadchecker.py txt
python uploadchecker.py csv
```

## Flags

- `-v`, `--verbose` - Show detailed output during execution
## Example Outputs

### CSV
![csv output](https://i.ibb.co/SmkvfV1/2024-04-03-19-38-21.png)

### TXT
<https://github.com/frenchcutgreenbean/UNIT3D-Upload-Checker/blob/uploadchecker/manual_txt_example.txt>

### GG
<https://github.com/frenchcutgreenbean/UNIT3D-Upload-Checker/blob/uploadchecker/manual_bot_example.txt>

## Safety Categories

### Safe
Files that don't exist on the tracker, or have a new resolution/quality that would be an upgrade.

### Risky  
Files that are likely a new quality, but are of a lower source than what's already uploaded. 
(For most trackers these are safe to upload, but I recommend doing it manually.) 'allow_risky' can be enabled in settings to push these into exports.

### Danger
Files that require careful review:
- Year from filename differs from TMDB match (and failed 2/3 backup checks)
- No English audio or subtitles found
- Existing on tracker and quality couldn't be determined from filename

## Automating Uploads
### Method 1
I recommend using the upgraded fork from @Audionut
https://github.com/Audionut/Upload-Assistant

This has support to call the output.txt file and upload all the safe matches using the --unit3d flag.

Can be called like:
```sh
py upload.py "outputs/aither_uploads.txt" --trackers "AITHER" -ua --unit3d

py upload.py "/home/user/bin/UNIT3D-Upload-Checker/outputs/lst_uploads.txt" --trackers "LST" -ua --unit3d
```


### Method 2
Or you can use `run_commands.py` on your `tracker_ua.txt` or `tracker_gg.txt`

Example calls:

```sh
python3 run_commands.py /path/to/outputs/lst_ua.txt
```

## Adding New Trackers

To add support for additional UNIT3D trackers:

1. Edit `tracker_info.json` with tracker details

Pull requests for new tracker support are welcome!

## Requirements

- Python 3.7+
- See `requirements.txt` for dependencies

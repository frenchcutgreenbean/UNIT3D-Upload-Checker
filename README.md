# UNIT3D Upload Checker

A command-line tool to scan directories for movies and check for duplicates across UNIT3D trackers.

## Features

- Scan directories for movies (.mkv only)
- Parse filenames then search on TMDB
- Use TMDB id + resolution (if found) to search trackers for unique movies
- Ability to ignore groups, qualities, and other keywords
- Scan files with mediainfo to ensure either English audio or English subtitles
- Export possible uploads to gg-bot commands and .txt or .csv files

## Sites Supported

- Aither
- Blutopia
- FearNoPeer
- LST
- OnlyEncodes
- ReelFliX
- Upload.cx

Any UNIT3D trackers can be supported by adding the necessary info.

## Quick Start

```sh
git clone https://github.com/frenchcutgreenbean/UNIT3D-Upload-Checker.git
cd UNIT3D-Upload-Checker

# Create and activate a virtual environment (recommended for all platforms)
python -m venv venv
source venv/bin/activate      # On Linux/macOS
venv\Scripts\activate         # On Windows

pip install -r requirements.txt
```

### Add Required Settings

Add directories to scan:
```sh
python uploadchecker.py setting-add directories /home/movies/
```

Add tracker API keys:
```sh
python uploadchecker.py setting-add blu <api_key>
python uploadchecker.py setting-add aith <api_key>
python uploadchecker.py setting-add fnp <api_key>
python uploadchecker.py setting-add rfx <api_key>
```

Enable sites:
```sh
python uploadchecker.py setting-add enabled_sites blu
python uploadchecker.py setting-add enabled_sites aith
```

Add your TMDB API key:
```sh
python uploadchecker.py setting-add tmdb_key <api_key>
```

Run the complete workflow:
```sh
python uploadchecker.py run-all -v
```

## Commands

### Workflow Commands

| Command    | Description                                               | Flags                |
|------------|-----------------------------------------------------------|----------------------|
| `run-all`  | Run complete workflow (scan → tmdb → search → save → export) | `-v`, `--no-mediainfo` |
| `scan`     | Scan directories for media files                          | `-v`                 |
| `tmdb`     | Search TMDB for movie information                         | `-v`                 |
| `search`   | Search trackers for duplicates                            | `-v`                 |
| `save`     | Create search data from results                           | `--no-mediainfo`     |

### Settings Commands

| Command        | Description                | Examples                                      |
|----------------|---------------------------|-----------------------------------------------|
| `setting`      | View current settings      | `python uploadchecker.py setting directories` |
| `setting-add`  | Add or update a setting    | `python uploadchecker.py setting-add tmdb_key YOUR_KEY` |
| `setting-rm`   | Remove a setting value     | `python uploadchecker.py setting-rm directories /old/path/` |

### Export Commands

| Command | Description                    |
|---------|--------------------------------|
| `txt`   | Export results to text format  |
| `csv`   | Export results to CSV format   |
| `gg`    | Export GG bot commands         |
| `ua`    | Export UA format               |

### Utility Commands

| Command      | Description                                 |
|--------------|---------------------------------------------|
| `clear-data` | Clear all stored scan and search data        |

## Command Line Examples

### Settings Management
```sh
# View specific setting
python uploadchecker.py setting directories

# Add a directory
python uploadchecker.py setting-add directories /home/user/movies/

# Add API key
python uploadchecker.py setting-add blu your_api_key_here

# Remove a directory
python uploadchecker.py setting-rm directories /old/path/

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
- `--no-mediainfo` - Skip mediainfo extraction (not recommended)

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
Files that are likely a new quality, but are of a lower source than what's already uploaded. For most trackers these are
safe to upload, but I recommend doing it manually. (example: Tracker has 1080p REMUX, You have 1080p WEB-DL.)

### Danger
Files that require careful review:
- Year from filename differs from TMDB match
- No English audio or subtitles found
- Existing on tracker but quality couldn't be determined from filename

## Adding New Trackers

To add support for additional UNIT3D trackers:

1. Edit `tracker_info.json` with tracker details
2. Update `settings.py`:
   - Add to `self.tracker_nicknames`
   - Add to `self.default_settings["keys"]`
3. Update `check.py`
    - Add to `TRACKER_MAP`
    
Pull requests for new tracker support are welcome!

## Requirements

- Python 3.7+
- See `requirements.txt` for dependencies

## Best Practices

- Always use a virtual environment for Python projects (`python -m venv venv`)
- Never install Python packages system-wide on Linux; use a virtual environment or `pipx` for CLI tools
- Use `--help` to explore available commands and options

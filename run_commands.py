import subprocess
import sys
from pathlib import Path

# Usage:
# if you are using a virtual environment
# python run_commands.py <file_path> <venv_key>
# if not using a virtual environment
# python run_commands.py <file_path>


# Update these to the correct paths
VENV_MAP = {
    "ua": "/home/user/bin/Upload-Assistant/venv/bin/python",
    "gg": "/home/user/bin/gg-bot/venv/bin/python",
}


file_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None

venv_key = sys.argv[2].lower() if len(sys.argv) > 2 else None

if not file_path or not file_path.exists():
    print(f"File not found: {file_path}")
    sys.exit(1)

venv_python = VENV_MAP.get(venv_key) if venv_key else None

with file_path.open() as f:
    for line in f:
        cmd = line.strip()
        if not cmd or cmd.startswith("#"):
            continue
        if venv_python and cmd.startswith("python3 "):
            cmd = cmd.replace("python3", venv_python, 1)
        subprocess.run(cmd, shell=True)

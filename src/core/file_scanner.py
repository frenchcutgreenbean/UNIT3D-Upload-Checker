#!/usr/bin/env python3
import math
import os
import re
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Generator

from ..utils.file_parser import FileParser
from ..utils.logger import get_logger

# Initialize logger
logger = get_logger()

# Constants
SUPPORTED_EXTENSIONS = {".mkv"}

# Directory-name based series detection (name-only heuristic)
SERIES_DIR_PATTERN = re.compile(
    r"(?:^|[\W_])(?:s(?:eason)?\s?\d{1,2}|s\d{1,2}|season\s*\d{1,2}|season[-_\s]?\d{1,2})(?:$|[\W_])",
    re.I,
)


class FileScanner:
    """Handles scanning directories for media files and extracting metadata."""

    def __init__(self, max_workers: int = 4):
        self.parser = FileParser()
        self.extract_filename = re.compile(r"^.*[\\/](.*)")
        self.scan_data: Dict[str, Dict] = {}
        self.max_workers = max_workers

    def scan_directories(self, directories: List[str], verbose: bool = False) -> bool:
        """Scan all configured directories for media files concurrently."""
        try:
            if verbose:
                logger.section("Scanning Directories")
                logger.info("Scanning directories for media files...")
            if not self._validate_directories(directories):
                return False

            # Scan each top-level configured directory in parallel (I/O bound -> threads)
            with ThreadPoolExecutor(max_workers=self.max_workers) as exc:
                futures = {exc.submit(self._scan_single_directory, d, verbose): d for d in directories}
                for fut in as_completed(futures):
                    try:
                        fut.result()
                    except Exception as e:
                        logger.error(f"Error scanning {futures[fut]}: {e}")
                        logger.debug(traceback.format_exc())

            return True
        except Exception as e:
            logger.error(f"Error scanning directories: {e}")
            logger.debug(traceback.format_exc())
            return False

    @staticmethod
    def _validate_directories(directories: List[str]) -> bool:
        """Validate that directories are configured and exist."""
        if not directories:
            logger.error("No directories configured")
            logger.info("Use: python uploadchecker.py add dir <directory_path>")
            return False

        for directory in directories:
            if not os.path.exists(directory):
                logger.error(f"Directory does not exist: {directory}")
                return False

        return True

    def _scan_single_directory(self, directory: str, verbose: bool = False):
        """Scan a single directory for media files."""
        dir_data = self.scan_data.get(directory, {})

        for file_path in self._get_media_files(directory, verbose):
            if self._should_skip_file(file_path, dir_data, verbose):
                continue

            file_data = self._process_media_file(file_path, verbose)
            if file_data:
                dir_data[file_data["file_name"]] = file_data

        self.scan_data[directory] = dir_data

    @staticmethod
    def _get_media_files(directory: str, verbose: bool = False) -> Generator[str, None, list[Any] | None]:
        """Yield media files in directory matching supported extensions using os.walk.

        Prune subdirectories purely by name (no inspection of their contents).
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            if verbose:
                logger.warning(f"Directory does not exist: {directory}")
            return []

        for root, dirs, files in os.walk(directory, topdown=True):
            # Name-only pruning: remove any subdir whose name matches the series pattern
            # so os.walk will not recurse into it.
            for subdir in list(dirs):
                if SERIES_DIR_PATTERN.search(subdir):
                    if verbose:
                        logger.debug(f"Skipping directory by name (series-like): {subdir}")
                    dirs.remove(subdir)

            for name in files:
                if os.path.splitext(name)[1].lower() in SUPPORTED_EXTENSIONS:
                    yield os.path.join(root, name)
        return None

    @staticmethod
    def _file_key(file_path: str) -> Tuple[int, float]:
        """Return lightweight fingerprint for file: (size_bytes, mtime)."""
        st = os.stat(file_path)
        return st.st_size, st.st_mtime

    def _should_skip_file(self, file_path: str, dir_data: Dict, verbose: bool) -> bool:
        """Check if file should be skipped by comparing file_key (size+mtime)."""
        file_name = self.extract_filename.match(file_path).group(1)
        try:
            key = self._file_key(file_path)
        except (OSError, PermissionError):
            if verbose:
                logger.warning(f"Cannot access {file_path}, skipping")
            return True

        existing = dir_data.get(file_name)
        if existing:
            existing_key = existing.get("file_key")
            if existing_key == key:
                if verbose:
                    logger.debug(f"{file_name} unchanged, skipping (cached).")
                return True
        return False

    def _process_media_file(self, file_path: str, verbose: bool) -> Optional[Dict]:
        """Process a single media file and extract basic metadata (no MediaInfo yet)."""
        try:
            file_name = self.extract_filename.match(file_path).group(1)
            st = os.stat(file_path)
            size_bytes = st.st_size
            file_size = self._convert_size(size_bytes)

            if verbose:
                logger.debug("=" * 80)
                logger.info(f"Scanning: {file_name}")
                logger.debug(f"File size: {file_size}")

            # Parse filename for basic metadata
            parsed_data = self.parser.parse_filename(file_name, verbose)

            return {
                "file_location": file_path,
                "file_name": file_name,
                "file_size": file_size,
                "file_key": (size_bytes, st.st_mtime),
                **parsed_data,
            }
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            logger.debug(traceback.format_exc())
            return None

    @staticmethod
    def _convert_size(size_bytes: int) -> str:
        """Convert bytes to human-readable format."""
        if size_bytes == 0:
            return "0B"
        size_name = ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_name[i]}"

    def get_scan_data(self) -> Dict:
        """Get the current scan data."""
        return self.scan_data.copy()


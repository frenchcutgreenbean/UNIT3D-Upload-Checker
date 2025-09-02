#!/usr/bin/env python3
import csv
import shlex
import sys
from pathlib import Path
from urllib.parse import quote
from typing import Dict

PY_VERSION = "py" if sys.platform.startswith("win") else "python3"


class ResultExporter:
    """Handles exporting search results in various formats."""

    def __init__(self, output_folder: str, tracker_info: Dict, settings_manager):
        self.output_folder = Path(output_folder)
        self.tracker_info = tracker_info
        self.settings = settings_manager
        self.output_folder.mkdir(exist_ok=True)

    def export_gg_commands(self, search_data: Dict) -> bool:
        """Export results as commands ready to use for uploading with gg_bot."""
        try:
            gg_path = self.settings.current_settings.get("gg_path")
            if not gg_path:
                print("gg_path not configured.")
                return False

            gg_dir = Path(gg_path)
            if gg_dir.name == "auto_upload.py":
                gg_dir = gg_dir.parent

            script_path = gg_dir / "auto_upload.py"
            allow_risky = self.settings.current_settings.get("allow_risky", False)

            for tracker, data in search_data.items():
                tracker_map = self.tracker_info.get(tracker, {}).get("map")
                if not tracker_map:
                    print(f"No map configured for tracker: {tracker}")
                    continue

                out_path = self.output_folder / f"{tracker}_gg.txt"
                tracker_flag = tracker_map

                with out_path.open("w") as f:
                    categories = ("safe", "risky") if allow_risky else ("safe",)

                    for category in categories:
                        for file_info in data.get(category, {}).values():
                            line = self._build_command_line(
                                PY_VERSION,
                                script_path,
                                "-p",
                                file_info["file_location"],
                                "-t",
                                tracker_flag,
                            )
                            f.write(line + "\n")

                print(f"Exported gg-bot auto_upload commands to {out_path}")

            return True
        except Exception as e:
            print(f"Error exporting gg-bot commands: {e}")
            return False

    def export_ua_commands(self, search_data: Dict) -> bool:
        """Export results as commands ready to use for uploading with upload assistant."""
        try:
            ua_path = self.settings.current_settings.get("ua_path")
            if not ua_path:
                print("ua_path not configured.")
                return False

            ua_dir = Path(ua_path)
            if ua_dir.name == "upload.py":
                ua_dir = ua_dir.parent

            script_path = ua_dir / "upload.py"
            allow_risky = self.settings.current_settings.get("allow_risky", False)

            for tracker, data in search_data.items():
                tracker_map = self.tracker_info.get(tracker, {}).get("map")
                if not tracker_map:
                    print(f"No map configured for tracker: {tracker}")
                    continue

                out_path = self.output_folder / f"{tracker}_ua.txt"
                tracker_flag = tracker_map

                with out_path.open("w") as f:
                    categories = ("safe", "risky") if allow_risky else ("safe",)

                    for category in categories:
                        for file_info in data.get(category, {}).values():
                            line = self._build_command_line(
                                PY_VERSION,
                                script_path,
                                "--trackers",
                                tracker_flag,
                                file_info["file_location"],
                            )
                            f.write(line + "\n")

                print(f"Exported Upload-Assistant commands to {out_path}")

            return True
        except Exception as e:
            print(f"Error exporting Upload-Assistant commands: {e}")
            return False

    def export_txt_format(self, search_data: Dict) -> bool:
        """Export possible uploads to manual.txt format."""
        try:
            for tracker, data in search_data.items():
                out_path = self.output_folder / f"{tracker}_uploads.txt"

                with out_path.open("w") as f:
                    for safety_level, files in data.items():
                        if not files:
                            continue

                        f.write(f"{safety_level}\n")

                        for title, file_info in files.items():
                            formatted_info = self._format_file_info_text(
                                title, file_info, tracker
                            )
                            f.write(formatted_info + "\n")

                print(f"Manual info saved to {out_path}")

            return True
        except Exception as e:
            print(f"Error writing uploads.txt: {e}")
            return False

    def export_csv_format(self, search_data: Dict) -> bool:
        """Export results in CSV format."""
        try:
            for tracker, data in search_data.items():
                out_path = self.output_folder / f"{tracker}_uploads.csv"

                with out_path.open("w", newline="", encoding="utf-8") as csvfile:
                    fieldnames = [
                        "Safety",
                        "Movie Title",
                        "File Year",
                        "TMDB Year",
                        "Quality",
                        "File Location",
                        "File Size",
                        "TMDB Search",
                        "String Search",
                        "TMDB URL",
                        "Reason",
                        "Details",
                        "Media Info",
                    ]

                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()

                    for safety_level, files in data.items():
                        for title, file_info in files.items():
                            row = self._format_file_info_csv(
                                title, file_info, tracker, safety_level
                            )
                            writer.writerow(row)

                print(f"Manual info saved to {out_path}")

            return True
        except Exception as e:
            print(f"Error writing uploads.csv: {e}")
            return False

    def _build_command_line(
        self, py_version: str, script_path: Path, *args: str
    ) -> str:
        """Build a command line string with proper escaping."""
        cmd = [py_version, str(script_path), *args]
        return " ".join(shlex.quote(arg) for arg in cmd)

    def _format_file_info_text(self, title: str, file_info: Dict, tracker: str) -> str:
        """Format file information for text export."""
        url_query = quote(title)
        tmdb = file_info.get("tmdb", "")
        tracker_url = self.tracker_info.get(tracker, {}).get("url", "")
        driver = self.tracker_info.get(tracker, {}).get("driver", "").lower()

        tmdb_url = f"https://www.themoviedb.org/movie/{tmdb}" if tmdb else "N/A"
        if driver == "unit3d":
            # Build URLs
            tracker_tmdb = (
                f"{tracker_url}torrents?view=list&tmdbId={tmdb}"
                if tmdb and tracker_url
                else "N/A"
            )
            tracker_string = (
                f"{tracker_url}torrents?view=list&name={url_query}"
                if tracker_url
                else "N/A"
            )
        else:
            tracker_tmdb = (
                f"{tracker_url}torrents?search=&tmdb=movie%2F{tmdb}"
                if tmdb and tracker_url
                else "N/A"
            )
            tracker_string = (
                f"{tracker_url}torrents?search={url_query}" if tracker_url else "N/A"
            )

        # Format media info
        media_info_str = self._format_media_info_text(file_info.get("media_info"))

        return f"""
        Movie Title: {title}
        File Year: {file_info.get('year', 'N/A')}
        TMDB Year: {file_info.get('tmdb_year', 'N/A')}
        Quality: {file_info.get('quality', 'N/A')}
        File Location: {file_info.get('file_location', 'N/A')}
        File Size: {file_info.get('file_size', 'N/A')}
        TMDB Search: {tracker_tmdb}
        String Search: {tracker_string}
        TMDB: {tmdb_url}
        Reason: {file_info.get('reason', 'N/A')}
        Details: {', '.join(file_info.get('details', []))}
        Media Info: {media_info_str}
        """

    def _format_file_info_csv(
        self, title: str, file_info: Dict, tracker: str, safety_level: str
    ) -> Dict:
        """Format file information for CSV export."""
        url_query = quote(title)
        tmdb = file_info.get("tmdb", "")
        tracker_url = self.tracker_info.get(tracker, {}).get("url", "")
        driver = self.tracker_info.get(tracker, {}).get("driver", "").lower()

        tmdb_url = f"https://www.themoviedb.org/movie/{tmdb}" if tmdb else "N/A"
        if driver == "unit3d":
            # Build URLs
            tracker_tmdb = (
                f"{tracker_url}torrents?view=list&tmdbId={tmdb}"
                if tmdb and tracker_url
                else "N/A"
            )
            tracker_string = (
                f"{tracker_url}torrents?view=list&name={url_query}"
                if tracker_url
                else "N/A"
            )
        else:
            tracker_tmdb = (
                f"{tracker_url}torrents?search=&tmdb=movie%2F{tmdb}"
                if tmdb and tracker_url
                else "N/A"
            )
            tracker_string = (
                f"{tracker_url}torrents?search={url_query}" if tracker_url else "N/A"
            )

        # Format media info for CSV (single line)
        media_info_str = self._format_media_info_csv(file_info.get("media_info"))

        return {
            "Safety": safety_level,
            "Movie Title": title,
            "File Year": file_info.get("year", "N/A"),
            "TMDB Year": file_info.get("tmdb_year", "N/A"),
            "Quality": file_info.get("quality", "N/A"),
            "File Location": file_info.get("file_location", "N/A"),
            "File Size": file_info.get("file_size", "N/A"),
            "TMDB Search": tracker_tmdb,
            "String Search": tracker_string,
            "TMDB URL": tmdb_url,
            "Reason": file_info.get("reason", "N/A"),
            "Details": ", ".join(file_info.get("details", [])),
            "Media Info": media_info_str,
        }

    def _format_media_info_text(self, media_info: Dict) -> str:
        """Format media info for text display."""
        if not media_info or media_info == "None":
            return "None"

        try:
            return f"""
            Language(s): {media_info.get('audio_language(s)', 'N/A')}
            Subtitle(s): {media_info.get('subtitle(s)', 'N/A')}
            Audio Info: {media_info.get('audio_info', 'N/A')}
            Video Info: {media_info.get('video_info', 'N/A')}
            HDR Type: {media_info.get('hdr_type', 'N/A')}
            Duration: {media_info.get('runtime', 'N/A')} min
            """
        except (AttributeError, KeyError):
            return str(media_info)

    def _format_media_info_csv(self, media_info: Dict) -> str:
        """Format media info for CSV (single line)."""
        if not media_info or media_info == "None":
            return "None"

        try:
            parts = [
                f"Language(s): {media_info.get('audio_language(s)', 'N/A')}",
                f"Subtitle(s): {media_info.get('subtitle(s)', 'N/A')}",
                f"Audio Info: {media_info.get('audio_info', 'N/A')}",
                f"Video Info: {media_info.get('video_info', 'N/A')}",
                f"HDR Type: {media_info.get('hdr_type', 'N/A')}",
                f"Duration: {media_info.get('runtime', 'N/A')} min",
            ]
            return ", ".join(parts)
        except (AttributeError, KeyError):
            return str(media_info)

#!/usr/bin/env python3
import argparse
import sys
from src.check import UploadChecker


def create_parser():
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        description="UNIT3D Upload Checker - Scan and check for duplicate uploads",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s scan -v                    # Scan directories with verbose output
  %(prog)s run-all -v                 # Run complete workflow with verbose output
  %(prog)s setting-add tmdb YOUR_KEY  # Add TMDB API key
  %(prog)s setting directories        # View current directories
  %(prog)s clear-data                 # Clear all stored data
        """,
    )

    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # === WORKFLOW COMMANDS ===

    # Scan command
    scan_parser = subparsers.add_parser("scan", help="Scan directories for media files")
    scan_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show detailed output"
    )

    # TMDB command
    tmdb_parser = subparsers.add_parser(
        "tmdb", help="Search TMDB for movie information"
    )
    tmdb_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show detailed output"
    )

    # Search command
    search_parser = subparsers.add_parser(
        "search", help="Search trackers for duplicates"
    )
    search_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show detailed output"
    )

    # Save command
    save_parser = subparsers.add_parser("save", help="Create search data from results")
    save_parser.add_argument(
        "--no-mediainfo", action="store_true", help="Skip mediainfo extraction"
    )

    # Run-all command
    runall_parser = subparsers.add_parser(
        "run-all", help="Run complete workflow (scan → tmdb → search → save → export)"
    )
    runall_parser.add_argument(
        "--no-mediainfo", action="store_true", help="Skip mediainfo extraction"
    )
    runall_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show detailed output"
    )

    # === SETTINGS COMMANDS ===

    # Settings view
    setting_parser = subparsers.add_parser("setting", help="View current settings")
    setting_parser.add_argument(
        "target",
        nargs="?",
        choices=[
            "directories",
            "tmdb_key",
            "enabled_sites",
            "gg_path",
            "ua_path",
            "search_cooldown",
            "min_file_size",
            "banned_groups",
            "ignored_qualities",
            "ignored_keywords",
        ],
        help="Specific setting to view (optional)",
    )

    # Settings add
    add_parser = subparsers.add_parser("setting-add", help="Add or update a setting")
    add_parser.add_argument(
        "target",
        choices=[
            "directories",
            "tmdb_key",
            "enabled_sites",
            "gg_path",
            "ua_path",
            "search_cooldown",
            "min_file_size",
            "banned_groups",
            "ignored_qualities",
            "ignored_keywords",
            "aith",
            "blu",
            "fnp",
            "rfx",
        ],
        help="Setting to add/update",
    )
    add_parser.add_argument("value", help="Value to set")

    # Settings remove
    rm_parser = subparsers.add_parser("setting-rm", help="Remove a setting")
    rm_parser.add_argument(
        "target",
        choices=[
            "directories",
            "enabled_sites",
            "banned_groups",
            "ignored_qualities",
            "ignored_keywords",
        ],
        help="Setting to remove",
    )
    rm_parser.add_argument(
        "value", nargs="?", help="Specific value to remove (for list settings)"
    )

    # === EXPORT COMMANDS ===

    subparsers.add_parser("txt", help="Export results to text format")
    subparsers.add_parser("csv", help="Export results to CSV format")
    subparsers.add_parser("gg", help="Export GG format")
    subparsers.add_parser("ua", help="Export UA format")

    # === UTILITY COMMANDS ===

    subparsers.add_parser("clear-data", help="Clear all stored scan and search data")

    return parser


def main():
    """Main entry point for the Upload Checker application."""
    parser = create_parser()
    args = parser.parse_args()

    # Show help if no command provided
    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Initialize checker
    try:
        ch = UploadChecker()
    except Exception as e:
        print(f"Failed to initialize Upload Checker: {e}")
        sys.exit(1)

    # Command mapping
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
        "ua": ch.export_ua,
    }

    try:
        func = FUNCTION_MAP[args.command]
        func_args = {}

        # Handle different argument patterns
        if args.command in ["scan", "tmdb", "search"]:
            if hasattr(args, "verbose"):
                func_args["verbose"] = args.verbose

        elif args.command in ["save", "run-all"]:
            if hasattr(args, "verbose"):
                func_args["verbose"] = args.verbose
            if hasattr(args, "no_mediainfo"):
                func_args["mediainfo"] = not args.no_mediainfo
            else:
                func_args["mediainfo"] = True

        elif args.command == "setting":
            if hasattr(args, "target") and args.target:
                func_args["target"] = args.target

        elif args.command == "setting-add":
            func_args["target"] = args.target
            func_args["value"] = args.value

        elif args.command == "setting-rm":
            func_args["target"] = args.target
            if hasattr(args, "value") and args.value:
                func_args["value"] = args.value

        # Execute the function
        result = func(**func_args)

        # Handle return codes
        if result is False:
            sys.exit(1)

    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

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
  %(prog)s init                       # Initialize configuration files  
  %(prog)s scan -v                    # Scan directories with verbose output
  %(prog)s run-all -v                 # Run complete workflow with verbose output
  %(prog)s add tmdb YOUR_KEY          # Add TMDB API key
  %(prog)s add dir                    # Add a directory
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
        "-v", "--verbose", action="store_true", help="Show detailed output"
    )

    # Run-all command
    runall_parser = subparsers.add_parser(
        "run-all", help="Run complete workflow (scan → tmdb → search → save → export)"
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
        help="Specific setting to view (optional)",
    )

    # Settings add
    add_parser = subparsers.add_parser("add", help="Add or update a setting")
    add_parser.add_argument(
        "target",
        help="Setting to add/update",
    )
    add_parser.add_argument("value", help="Value to set")

    # Settings remove
    rm_parser = subparsers.add_parser("rm", help="Remove a setting")
    rm_parser.add_argument(
        "target",
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

    subparsers.add_parser("init", help="Initialize data files and configuration")
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

    # Handle init command specially (doesn't need UploadChecker instance)
    if args.command == "init":
        try:
            from src.settings import Settings
            from src.core import DataManager
            from pathlib import Path
            
            print("Initializing UNIT3D Upload Checker...")
            
            # Initialize settings (creates data dir and settings.json)
            settings = Settings()
            print("✅ Created data directory and settings.json")
            
            # Initialize data manager files 
            data_manager = DataManager()
            enabled_sites = settings.current_settings.get("enabled_sites", [])
            success = data_manager.initialize_files(enabled_sites)
            if success:
                print("✅ Created database.json and search_data.json")
            else:
                print("⚠️  Warning: Some data files may not have been created")
            
            # Create outputs directory
            outputs_dir = Path("outputs")
            outputs_dir.mkdir(exist_ok=True)
            print("✅ Created outputs directory")
            
            print(f"\n🎉 Initialization complete!")
            print(f"📁 Configuration: data/settings.json")
            print(f"📁 Data files: data/")
            print(f"📁 Output files: outputs/")
            print(f"\nNext steps:")
            print(f"  1. Add your TMDB API key: python uploadchecker.py add tmdb YOUR_KEY")
            print(f"  2. Add directories to scan: python uploadchecker.py add dir /path/to/movies")
            print(f"  3. Configure tracker API keys in data/settings.json")
            print(f"  4. Run the workflow: python uploadchecker.py run-all -v")
            
            return
            
        except Exception as e:
            print(f"❌ Error during initialization: {e}")
            sys.exit(1)

    # Initialize checker for all other commands
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
        "add": ch.update_setting,
        "rm": ch.remove_setting,
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

        elif args.command == "setting":
            if hasattr(args, "target") and args.target:
                func_args["target"] = args.target

        elif args.command == "add":
            func_args["target"] = args.target
            func_args["value"] = args.value

        elif args.command == "rm":
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

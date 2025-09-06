#!/usr/bin/env python3
import argparse
import sys
import traceback

# Import logger early to make it available for all modules
from src.utils.logger import get_logger

logger = get_logger()

# Only import UploadChecker after logger is configured
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
    scan_parser.add_argument(
        "--log", action="store_true", help="Enable file logging"
    )

    # TMDB command
    tmdb_parser = subparsers.add_parser(
        "tmdb", help="Search TMDB for movie information"
    )
    tmdb_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show detailed output"
    )
    tmdb_parser.add_argument(
        "--log", action="store_true", help="Enable file logging"
    )

    # Search command
    search_parser = subparsers.add_parser(
        "search", help="Search trackers for duplicates"
    )
    search_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show detailed output"
    )
    search_parser.add_argument(
        "--log", action="store_true", help="Enable file logging"
    )

    # Save command
    save_parser = subparsers.add_parser("save", help="Create search data from results")
    save_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show detailed output"
    )
    save_parser.add_argument(
        "--log", action="store_true", help="Enable file logging"
    )

    # Run-all command
    runall_parser = subparsers.add_parser(
        "run-all", help="Run complete workflow (scan → tmdb → search → save → export)"
    )
    runall_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show detailed output"
    )
    runall_parser.add_argument(
        "--log", action="store_true", help="Enable file logging"
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

    txt_parser = subparsers.add_parser("txt", help="Export results to text format")
    txt_parser.add_argument(
        "--log", action="store_true", help="Enable file logging"
    )
    
    csv_parser = subparsers.add_parser("csv", help="Export results to CSV format")
    csv_parser.add_argument(
        "--log", action="store_true", help="Enable file logging"
    )
    
    gg_parser = subparsers.add_parser("gg", help="Export GG format")
    gg_parser.add_argument(
        "--log", action="store_true", help="Enable file logging"
    )
    
    ua_parser = subparsers.add_parser("ua", help="Export UA format")
    ua_parser.add_argument(
        "--log", action="store_true", help="Enable file logging"
    )

    # === UTILITY COMMANDS ===

    subparsers.add_parser("init", help="Initialize data files and configuration")
    subparsers.add_parser("clear-data", help="Clear all stored scan and search data")

    return parser


def main():
    """Main entry point for the script."""
    parser = create_parser()
    args = parser.parse_args()

    # Show help if no command is provided
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Setup logging if requested
    if hasattr(args, 'log') and args.log:
        verbose = hasattr(args, 'verbose') and args.verbose
        logger.setup_file_logging(verbose)
        logger.debug("File logging enabled")

    # Handle init command specially (doesn't need UploadChecker instance)
    if args.command == "init":
        try:
            from src.settings import Settings
            from src.core import DataManager
            from pathlib import Path
            
            logger.section("Initializing UNIT3D Upload Checker")
            
            # Initialize settings (creates data dir and settings.json)
            settings = Settings()
            logger.success("Created data directory and settings.json")
            
            # Initialize data manager files 
            data_manager = DataManager()
            enabled_sites = settings.current_settings.get("enabled_sites", [])
            success = data_manager.initialize_files(enabled_sites)
            if success:
                logger.success("Created database.json and search_data.json")
            else:
                logger.warning("Some data files may not have been created")
        except Exception as e:
            logger.error(f"Failed to initialize Upload Checker: {e}")
            sys.exit(1)
        
        # Create outputs directory
        outputs_dir = Path("outputs")
        outputs_dir.mkdir(exist_ok=True)
        # Create .gitignore in outputs directory if it doesn't exist
        gitignore_file = outputs_dir / ".gitignore"
        if not gitignore_file.exists():
            with open(gitignore_file, "w") as f:
                f.write("# Ignore everything in this directory\n*\n# Except this file\n!.gitignore\n")
            logger.success("Created outputs directory with .gitignore")
        else:
            logger.success("Outputs directory already exists")
            
        # Create logs directory
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        # Create .gitignore in logs directory if it doesn't exist
        gitignore_file = logs_dir / ".gitignore"
        if not gitignore_file.exists():
            with open(gitignore_file, "w") as f:
                f.write("# Ignore everything in this directory\n*\n# Except this file\n!.gitignore\n")
            logger.success("Created logs directory with .gitignore")
        else:
            logger.success("Logs directory already exists")
            
        logger.success("Initialization complete")
        logger.info("You can now add settings with 'python uploadchecker.py add <setting> <value>'")
        logger.info("Example: python uploadchecker.py add dir /home/movies/")
        
        return

    # Initialize checker for all other commands
    try:
        ch = UploadChecker()
    except Exception as e:
        logger.error(f"Failed to initialize Upload Checker: {e}")
        logger.debug(traceback.format_exc())
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
        logger.info("\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        logger.debug(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()

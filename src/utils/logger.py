import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Define log levels with colors and formatting
class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for different log levels."""
    
    COLORS = {
        'DEBUG': '\033[36m',  # Cyan
        'INFO': '',           # No color
        'WARNING': '\033[33m', # Yellow
        'ERROR': '\033[31m',  # Red
        'CRITICAL': '\033[41m\033[37m',  # White on Red background
        'RESET': '\033[0m'    # Reset
    }
    
    def format(self, record):
        log_message = super().format(record)
        if record.levelname in self.COLORS and self.COLORS[record.levelname]:
            return f"{self.COLORS[record.levelname]}{log_message}{self.COLORS['RESET']}"
        return log_message

class Logger:
    """Unified logging handler for console and file output."""
    
    def __init__(self):
        self.logger = logging.getLogger("uploadchecker")
        self.logger.setLevel(logging.INFO)
        self.log_file = None
        
        # Prevent adding handlers multiple times
        if not self.logger.handlers:
            # Console handler
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(ColoredFormatter('%(message)s'))
            self.logger.addHandler(console_handler)
    
    def setup_file_logging(self, verbose: bool = False) -> None:
        """Setup file logging with timestamp in filename."""
        # Remove existing file handlers
        self.logger.handlers = [h for h in self.logger.handlers 
                               if not isinstance(h, logging.FileHandler)]
        
        # Set log level based on verbose flag
        self.logger.setLevel(logging.DEBUG if verbose else logging.INFO)
        
        # Create logs directory if it doesn't exist
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        
        # Create log file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = logs_dir / f"uploadchecker_{timestamp}.log"
        
        # Add file handler
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # Log initial message
        self.logger.info(f"Log file created: {self.log_file}")
    
    def debug(self, message: str) -> None:
        """Log debug message (only shown with verbose flag)."""
        self.logger.debug(message)
    
    def info(self, message: str) -> None:
        """Log info message."""
        self.logger.info(message)
    
    def success(self, message: str) -> None:
        """Log success message (INFO level with visual indicator)."""
        self.logger.info(f"✅ {message}")
    
    def warning(self, message: str) -> None:
        """Log warning message."""
        self.logger.warning(f"⚠️  {message}")
    
    def error(self, message: str) -> None:
        """Log error message."""
        self.logger.error(f"❌ {message}")
    
    def section(self, title: str) -> None:
        """Log a section header."""
        self.logger.info(f"\n--- {title} ---")

# Global logger instance
logger = Logger()

def get_logger() -> Logger:
    """Get the global logger instance."""
    return logger

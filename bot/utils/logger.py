
# File 10: bot/utils/logger.py
logger_py = '''"""
Bexo Downloader - Logging Configuration
Professional logging setup with multiple handlers and formatters
"""

import logging
import logging.handlers
import sys
from datetime import datetime
from pathlib import Path

from bot.config.settings import Settings


class ColoredFormatter(logging.Formatter):
    """Custom formatter with color support for console output."""
    
    COLORS = {
        "DEBUG": "\033[36m",      # Cyan
        "INFO": "\033[32m",       # Green
        "WARNING": "\033[33m",    # Yellow
        "ERROR": "\033[31m",      # Red
        "CRITICAL": "\033[35m",   # Magenta
        "RESET": "\033[0m",       # Reset
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        reset = self.COLORS["RESET"]
        record.levelname = f"{color}{record.levelname}{reset}"
        return super().format(record)


def setup_logging() -> None:
    """Setup professional logging configuration."""
    # Create logs directory
    logs_dir = Path("bot/logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    # Get log level from settings
    settings = Settings()
    log_level = getattr(logging, settings.log_level, logging.INFO)
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_format = ColoredFormatter(
        "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)
    
    # File handlers for different log types
    # Main bot log
    bot_handler = logging.handlers.RotatingFileHandler(
        logs_dir / "bot.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8"
    )
    bot_handler.setLevel(log_level)
    bot_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-20s | %(funcName)-20s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    bot_handler.setFormatter(bot_format)
    root_logger.addHandler(bot_handler)
    
    # Error log
    error_handler = logging.handlers.RotatingFileHandler(
        logs_dir / "error.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=10,
        encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-20s | %(funcName)-20s | %(lineno)d | %(message)s\n%(exc_info)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    error_handler.setFormatter(error_format)
    root_logger.addHandler(error_handler)
    
    # Download log
    download_handler = logging.handlers.RotatingFileHandler(
        logs_dir / "download.log",
        maxBytes=20 * 1024 * 1024,
        backupCount=10,
        encoding="utf-8"
    )
    download_handler.setLevel(logging.INFO)
    download_format = logging.Formatter(
        "%(asctime)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    download_handler.setFormatter(download_format)
    download_logger = logging.getLogger("bexo.download")
    download_logger.addHandler(download_handler)
    download_logger.setLevel(logging.INFO)
    
    # Admin log
    admin_handler = logging.handlers.RotatingFileHandler(
        logs_dir / "admin.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8"
    )
    admin_handler.setLevel(logging.INFO)
    admin_format = logging.Formatter(
        "%(asctime)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    admin_handler.setFormatter(admin_format)
    admin_logger = logging.getLogger("bexo.admin")
    admin_logger.addHandler(admin_handler)
    admin_logger.setLevel(logging.INFO)
    
    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
'''

with open("/mnt/agents/output/bexo_downloader/bot/utils/logger.py", "w", encoding="utf-8") as f:
    f.write(logger_py)

print("✅ bot/utils/logger.py created")

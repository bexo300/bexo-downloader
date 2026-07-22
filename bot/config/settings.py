"""
Bexo Downloader - Configuration Settings
Handles all environment variables and bot configuration
"""

import os
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Settings:
    """Bot configuration settings loaded from environment variables."""
    
    def __init__(self) -> None:
        """Initialize settings from environment variables."""
        # Bot Configuration
        self.bot_token: str = self._get_required("BOT_TOKEN")
        self.admin_ids: List[int] = self._parse_admin_ids()
        
        # Channel Subscription
        self.force_sub_channel: Optional[str] = os.getenv("FORCE_SUB_CHANNEL")
        
        # Database
        self.database_url: str = os.getenv(
            "DATABASE_URL", 
            "sqlite:///bot/database/bexo.db"
        )
        
        # Logging
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()
        
        # Paths
        self.download_path: Path = Path(
            os.getenv("DOWNLOAD_PATH", "bot/downloads")
        )
        self.download_path.mkdir(parents=True, exist_ok=True)
        
        # Cache
        self.cache_size: int = int(os.getenv("CACHE_SIZE", "1000"))
        
        # Limits
        self.max_file_size: int = int(
            os.getenv("MAX_FILE_SIZE", "2048")
        )  # MB
        self.max_concurrent_downloads: int = int(
            os.getenv("MAX_CONCURRENT_DOWNLOADS", "5")
        )
        
        # FFmpeg
        self.ffmpeg_path: Optional[str] = os.getenv("FFMPEG_PATH") or None
        
        # Language
        self.default_language: str = os.getenv("DEFAULT_LANGUAGE", "ar")
        
        # Validate settings
        self._validate()
    
    def _get_required(self, key: str) -> str:
        """Get a required environment variable."""
        value = os.getenv(key)
        if not value:
            raise ValueError(f"Required environment variable '{key}' is not set")
        return value
    
    def _parse_admin_ids(self) -> List[int]:
        """Parse admin IDs from comma-separated string."""
        admin_ids_str = os.getenv("ADMIN_IDS", "")
        if not admin_ids_str:
            return []
        try:
            return [int(id_str.strip()) for id_str in admin_ids_str.split(",")]
        except ValueError:
            raise ValueError("ADMIN_IDS must be comma-separated integers")
    
    def _validate(self) -> None:
        """Validate configuration settings."""
        if not self.bot_token or len(self.bot_token) < 20:
            raise ValueError("Invalid BOT_TOKEN")
        
        if self.max_file_size > 2048:
            raise ValueError("MAX_FILE_SIZE cannot exceed 2048 MB (Telegram limit)")
        
        if self.max_concurrent_downloads < 1:
            raise ValueError("MAX_CONCURRENT_DOWNLOADS must be at least 1")
        
        if self.cache_size < 100:
            raise ValueError("CACHE_SIZE must be at least 100")
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return os.getenv("ENVIRONMENT", "development").lower() == "production"

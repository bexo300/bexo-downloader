
# File 6: main.py
main_py = '''#!/usr/bin/env python3
"""
Bexo Downloader - Main Entry Point
Professional Telegram Bot for Media Downloads

Author: Bexo Team
Version: 1.0.0
License: MIT
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from bot.config.settings import Settings
from bot.utils.logger import setup_logging
from bot.database.manager import DatabaseManager
from bot.services.downloader_service import DownloaderService
from bot.services.cache_service import CacheService
from bot.bot import BexoBot


async def main() -> None:
    """Main entry point for the Bexo Downloader bot."""
    # Setup logging first
    setup_logging()
    logger = logging.getLogger("bexo.main")
    
    logger.info("=" * 60)
    logger.info("🚀 Bexo Downloader v1.0.0")
    logger.info("Starting bot initialization...")
    logger.info("=" * 60)
    
    try:
        # Initialize settings
        settings = Settings()
        logger.info("✅ Settings loaded")
        
        # Initialize database
        db_manager = DatabaseManager(settings.database_url)
        await db_manager.init()
        logger.info("✅ Database initialized")
        
        # Initialize cache service
        cache_service = CacheService(settings.cache_size)
        logger.info("✅ Cache service initialized")
        
        # Initialize downloader service
        downloader_service = DownloaderService(
            max_concurrent=settings.max_concurrent_downloads,
            download_path=settings.download_path,
            max_file_size=settings.max_file_size,
            ffmpeg_path=settings.ffmpeg_path,
        )
        logger.info("✅ Downloader service initialized")
        
        # Initialize and run bot
        bot = BexoBot(
            token=settings.bot_token,
            admin_ids=settings.admin_ids,
            force_sub_channel=settings.force_sub_channel,
            db_manager=db_manager,
            cache_service=cache_service,
            downloader_service=downloader_service,
            default_language=settings.default_language,
        )
        
        logger.info("🤖 Starting bot...")
        await bot.run()
        
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
    except Exception as e:
        logger.exception(f"❌ Fatal error: {e}")
        sys.exit(1)
    finally:
        logger.info("🧹 Cleanup completed")


if __name__ == "__main__":
    # Use uvloop on Linux for better performance
    if sys.platform == "linux":
        try:
            import uvloop
            uvloop.install()
        except ImportError:
            pass
    
    asyncio.run(main())
'''

with open("/mnt/agents/output/bexo_downloader/main.py", "w", encoding="utf-8") as f:
    f.write(main_py)

print("✅ main.py created")

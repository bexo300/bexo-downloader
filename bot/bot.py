"""
Bexo Downloader - Main Bot Class
"""

import logging

from telegram.ext import Application, ApplicationBuilder

from bot.config.settings import Settings
from bot.database.manager import DatabaseManager
from bot.handlers.admin import AdminHandlers
from bot.handlers.user import UserHandlers
from bot.middlewares.rate_limiter import RateLimiter
from bot.services.cache_service import CacheService
from bot.services.downloader_service import DownloaderService


logger = logging.getLogger("bexo.bot")


class BexoBot:
    """Main bot class."""
    
    def __init__(
        self,
        token: str,
        admin_ids: list[int],
        force_sub_channel: Optional[str],
        db_manager: DatabaseManager,
        cache_service: CacheService,
        downloader_service: DownloaderService,
        default_language: str = "ar"
    ) -> None:
        """Initialize bot.
        
        Args:
            token: Bot token
            admin_ids: Admin IDs
            force_sub_channel: Force subscription channel
            db_manager: Database manager
            cache_service: Cache service
            downloader_service: Downloader service
            default_language: Default language
        """
        self.token = token
        self.admin_ids = admin_ids
        self.force_sub_channel = force_sub_channel
        self.db = db_manager
        self.cache = cache_service
        self.downloader = downloader_service
        self.default_language = default_language
        
        # Rate limiter
        self.rate_limiter = RateLimiter()
        
        # Build application
        self.application = (
            ApplicationBuilder()
            .token(token)
            .concurrent_updates(True)
            .build()
        )
        
        self._setup_handlers()
    
    def _setup_handlers(self) -> None:
        """Setup all handlers."""
        # User handlers
        user_handlers = UserHandlers(
            db_manager=self.db,
            cache_service=self.cache,
            downloader_service=self.downloader,
            force_sub_channel=self.force_sub_channel,
            default_language=self.default_language
        )
        
        for handler in user_handlers.get_handlers():
            self.application.add_handler(handler)
        
        # Admin handlers
        if self.admin_ids:
            admin_handlers = AdminHandlers(self.admin_ids, self.db)
            for handler in admin_handlers.get_handlers():
                self.application.add_handler(handler)
        
        # Error handler
        self.application.add_error_handler(self._error_handler)
    
    async def _error_handler(
        self,
        update: object,
        context: object
    ) -> None:
        """Handle errors.
        
        Args:
            update: Update that caused error
            context: Bot context
        """
        logger.error(f"Error: {context.error}")
    
    async def run(self) -> None:
        """Run the bot."""
        logger.info("Starting bot polling...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(drop_pending_updates=True)
        
        # Keep running
        import asyncio
        try:
            while True:
                await asyncio.sleep(3600)
                # Periodic cleanup
                await self.downloader.cleanup_downloads()
        except asyncio.CancelledError:
            pass
        finally:
            await self.application.stop()

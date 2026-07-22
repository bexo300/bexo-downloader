"""
Bexo Downloader - User Handlers
Main user interaction handlers
"""

import asyncio
import logging
import uuid
from pathlib import Path

from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.database.manager import DatabaseManager
from bot.keyboards.inline import cancel_keyboard, format_keyboard, quality_keyboard
from bot.locales import get_text
from bot.services.cache_service import CacheService
from bot.services.downloader_service import DownloaderService
from bot.utils.helpers import (
    calculate_eta,
    extract_platform,
    format_duration,
    format_number,
    format_size,
    generate_progress_bar,
    get_platform_icon,
    is_valid_url,
)


logger = logging.getLogger("bexo.handlers.user")


class UserHandlers:
    """Handles all user interactions."""
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        cache_service: CacheService,
        downloader_service: DownloaderService,
        force_sub_channel: Optional[str] = None,
        default_language: str = "ar"
    ) -> None:
        """Initialize user handlers.
        
        Args:
            db_manager: Database manager
            cache_service: Cache service
            downloader_service: Downloader service
            force_sub_channel: Required channel for subscription
            default_language: Default language code
        """
        self.db = db_manager
        self.cache = cache_service
        self.downloader = downloader_service
        self.force_sub_channel = force_sub_channel
        self.default_language = default_language
    
    def get_handlers(self):
        """Get all handlers for registration."""
        return [
            CommandHandler("start", self.start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_url),
            CallbackQueryHandler(self.handle_callback, pattern="^(dl:|format:|cancel)"),
        ]
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command.
        
        Args:
            update: Telegram update
            context: Bot context
        """
        user = update.effective_user
        lang = self.default_language
        
        # Check force subscription
        if self.force_sub_channel:
            try:
                member = await context.bot.get_chat_member(
                    f"@{self.force_sub_channel}",
                    user.id
                )
                if member.status in ["left", "kicked"]:
                    await update.message.reply_text(
                        get_text("force_sub", lang, channel=f"@{self.force_sub_channel}")
                    )
                    return
            except Exception:
                pass
        
        # Get or create user
        db_user = await self.db.get_user(user.id)
        if not db_user:
            db_user = await self.db.create_user(
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                language=lang
            )
        
        # Check ban
        if db_user.is_banned:
            await update.message.reply_text(get_text("banned", lang))
            return
        
        await update.message.reply_text(
            get_text("welcome", lang),
            parse_mode="HTML"
        )
    
    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle URL message.
        
        Args:
            update: Telegram update
            context: Bot context
        """
        user = update.effective_user
        lang = self.default_language
        url = update.message.text.strip()
        
        # Validate URL
        if not is_valid_url(url):
            await update.message.reply_text(get_text("invalid_url", lang))
            return
        
        # Extract platform
        platform = extract_platform(url)
        if not platform or not self.downloader.is_platform_supported(platform):
            await update.message.reply_text(get_text("not_supported", lang))
            return
        
        # Check cache
        cached_info = self.cache.get_media_info(url)
        if cached_info:
            info = cached_info
        else:
            # Get media info
            processing_msg = await update.message.reply_text(
                get_text("processing", lang)
            )
            
            info = await self.downloader.get_media_info(url)
            
            if processing_msg:
                await processing_msg.delete()
            
            if not info:
                await update.message.reply_text(get_text("video_private", lang))
                return
            
            self.cache.set_media_info(url, info)
        
        # Store in context
        context.user_data["current_url"] = url
        context.user_data["current_platform"] = platform
        
        # Show media info
        qualities = ", ".join([f"{f['height']}p" for f in info.get("formats", [])[:5]])
        duration = format_duration(info["duration"]) if info.get("duration") else "N/A"
        views = format_number(info["view_count"]) if info.get("view_count") else "N/A"
        
        platform_icon = get_platform_icon(platform)
        
        message = get_text(
            "media_info",
            lang,
            title=info.get("title", "Unknown")[:100],
            duration=duration,
            uploader=info.get("uploader", "Unknown")[:50],
            views=views,
            qualities=qualities or "Best"
        )
        
        # Show format/quality selection
        formats = info.get("formats", [])
        if formats:
            keyboard = quality_keyboard(
                [str(f["height"]) for f in formats[:8]],
                lang
            )
        else:
            keyboard = format_keyboard(lang)
        
        await update.message.reply_text(
            f"{platform_icon} {message}",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    
    async def handle_callback(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle callback queries.
        
        Args:
            update: Telegram update
            context: Bot context
        """
        query = update.callback_query
        await query.answer()
        
        user = update.effective_user
        lang = self.default_language
        data = query.data
        
        if data == "cancel":
            await query.edit_message_text("❌ تم الإلغاء")
            return
        
        url = context.user_data.get("current_url")
        if not url:
            await query.edit_message_text(get_text("error", lang, error="Session expired"))
            return
        
        # Parse callback data
        if data.startswith("dl:"):
            _, media_type, *quality = data.split(":")
            quality = quality[0] if quality else None
            
            await self._start_download(
                update, context, url, media_type, quality
            )
        
        elif data.startswith("format:"):
            _, media_type = data.split(":")
            await self._start_download(
                update, context, url, media_type, None
            )
    
    async def _start_download(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        url: str,
        media_type: str,
        quality: Optional[str]
    ) -> None:
        """Start download process.
        
        Args:
            update: Telegram update
            context: Bot context
            url: Media URL
            media_type: Type of media
            quality: Video quality
        """
        query = update.callback_query
        lang = self.default_language
        download_id = str(uuid.uuid4())[:8]
        
        # Progress callback
        last_update = [0]
        
        async def progress_callback(progress):
            now = asyncio.get_event_loop().time()
            if now - last_update[0] < 2:  # Update every 2 seconds
                return
            last_update[0] = now
            
            progress_bar = generate_progress_bar(progress.percentage)
            speed = format_size(int(progress.speed)) + "/s" if progress.speed else "N/A"
            eta = calculate_eta(
                int(progress.downloaded),
                int(progress.total),
                progress.speed
            )
            
            try:
                await query.edit_message_text(
                    get_text(
                        "downloading",
                        lang,
                        progress_bar=progress_bar,
                        percentage=f"{progress.percentage:.1f}",
                        speed=speed,
                        eta=eta
                    ),
                    parse_mode="HTML"
                )
            except Exception:
                pass
        
        # Update to downloading status
        await query.edit_message_text(
            get_text("downloading", lang, progress_bar=generate_progress_bar(0), percentage="0", speed="N/A", eta="N/A"),
            parse_mode="HTML"
        )
        
        # Download
        audio_only = media_type == "audio"
        file_path = await self.downloader.download(
            url=url,
            download_id=download_id,
            quality=quality,
            audio_only=audio_only,
            progress_callback=progress_callback
        )
        
        if not file_path:
            await query.edit_message_text(
                get_text("error", lang, error="Download failed")
            )
            return
        
        # Upload to user
        try:
            await query.edit_message_text(get_text("uploading", lang))
            
            if audio_only:
                await context.bot.send_audio(
                    chat_id=update.effective_chat.id,
                    audio=open(file_path, "rb"),
                    title=file_path.stem[:100]
                )
            else:
                await context.bot.send_video(
                    chat_id=update.effective_chat.id,
                    video=open(file_path, "rb"),
                    supports_streaming=True
                )
            
            await query.edit_message_text(get_text("completed", lang))
            
            # Update stats
            await self.db.increment_downloads(
                update.effective_user.id,
                "audio" if audio_only else "video"
            )
            
        except Exception as e:
            logger.error(f"Upload error: {e}")
            await query.edit_message_text(
                get_text("error", lang, error=str(e))
            )
        
        finally:
            # Cleanup
            if file_path and file_path.exists():
                file_path.unlink()

"""
Bexo Downloader - Admin Handlers
Admin panel and management commands
"""

import logging
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.database.manager import DatabaseManager
from bot.keyboards.inline import admin_keyboard
from bot.locales import get_text


logger = logging.getLogger("bexo.handlers.admin")

# Conversation states
BROADCAST, BAN_USER, UNBAN_USER = range(3)


class AdminHandlers:
    """Handles all admin interactions."""
    
    def __init__(self, admin_ids: list[int], db_manager: DatabaseManager) -> None:
        """Initialize admin handlers.
        
        Args:
            admin_ids: List of admin Telegram IDs
            db_manager: Database manager
        """
        self.admin_ids = admin_ids
        self.db = db_manager
    
    def get_handlers(self):
        """Get all handlers for registration."""
        return [
            CommandHandler("admin", self.admin_panel),
            CallbackQueryHandler(self.handle_admin_callback, pattern="^admin:"),
            ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(
                        self.start_broadcast,
                        pattern="^admin:broadcast$"
                    )
                ],
                states={
                    BROADCAST: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND,
                            self.send_broadcast
                        )
                    ]
                },
                fallbacks=[CommandHandler("cancel", self.cancel_conversation)],
            ),
        ]
    
    async def admin_panel(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Show admin panel.
        
        Args:
            update: Telegram update
            context: Bot context
        """
        user = update.effective_user
        
        if user.id not in self.admin_ids:
            return
        
        stats = await self.db.get_stats()
        
        # Get today's downloads
        today = datetime.utcnow().date()
        
        message = get_text(
            "admin_panel",
            "ar",
            users=stats["total_users"],
            downloads=stats["total_downloads"],
            today="N/A",
            month="N/A"
        )
        
        await update.message.reply_text(
            message,
            reply_markup=admin_keyboard(),
            parse_mode="HTML"
        )
    
    async def handle_admin_callback(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle admin callback queries.
        
        Args:
            update: Telegram update
            context: Bot context
        """
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "admin:stats":
            stats = await self.db.get_stats()
            message = (
                f"📊 <b>Statistics</b>\n\n"
                f"👥 Total Users: {stats['total_users']}\n"
                f"📥 Total Downloads: {stats['total_downloads']}\n"
                f"🎬 Videos: {stats['video_downloads']}\n"
                f"🎵 Audio: {stats['audio_downloads']}\n"
                f"🖼 Images: {stats['image_downloads']}"
            )
            await query.edit_message_text(message, parse_mode="HTML")
        
        elif data == "admin:users":
            top_users = await self.db.get_top_users(10)
            message = "🏆 <b>Top Users</b>\\n\\n"
            for i, user in enumerate(top_users, 1):
                name = user.first_name or user.username or f"User_{user.telegram_id}"
                message += f"{i}. {name}: {user.total_downloads} downloads\\n"
            
            await query.edit_message_text(message, parse_mode="HTML")
    
    async def start_broadcast(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Start broadcast conversation.
        
        Args:
            update: Telegram update
            context: Bot context
            
        Returns:
            BROADCAST state
        """
        query = update.callback_query
        await query.edit_message_text(
            "📢 Send the message to broadcast:\\n\\n"
            "Send /cancel to cancel."
        )
        return BROADCAST
    
    async def send_broadcast(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Send broadcast message to all users.
        
        Args:
            update: Telegram update
            context: Bot context
            
        Returns:
            Conversation end
        """
        message = update.message.text
        users = await self.db.get_all_users()
        
        sent = 0
        failed = 0
        
        for user in users:
            try:
                await context.bot.send_message(
                    chat_id=user.telegram_id,
                    text=message,
                    parse_mode="HTML"
                )
                sent += 1
            except Exception:
                failed += 1
        
        await update.message.reply_text(
            f"✅ Broadcast complete!\\n"
            f"Sent: {sent}\\n"
            f"Failed: {failed}"
        )
        
        return ConversationHandler.END
    
    async def cancel_conversation(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Cancel conversation.
        
        Args:
            update: Telegram update
            context: Bot context
            
        Returns:
            Conversation end
        """
        await update.message.reply_text("❌ Cancelled")
        return ConversationHandler.END

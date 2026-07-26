import os
import json
import time
from pathlib import Path
from typing import List, Dict, Any
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from config import Config
from utils import logger, format_size, safe_remove

CHANNELS_FILE = Path(Config.TEMP_DIR).parent / "channels.json"
ADMIN_MENU, ADD_CHANNEL, REMOVE_CHANNEL, BROADCAST, STATS, CLEANUP = range(6)

class AdminSystem:
    @staticmethod
    def load_channels():
        try:
            if CHANNELS_FILE.exists():
                with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"خطأ في تحميل القنوات: {e}")
            return []
    
    @staticmethod
    def save_channels(channels: List[str]):
        try:
            with open(CHANNELS_FILE, "w", encoding="utf-8") as f:
                json.dump(channels, f, ensure_ascii=False, indent=2)
            Config.FORCED_CHANNELS = channels
            return True
        except Exception as e:
            logger.error(f"خطأ في حفظ القنوات: {e}")
            return False
    
    @staticmethod
    def is_admin(user_id: int) -> bool:
        return user_id in Config.ADMINS
    
    @staticmethod
    def get_channels() -> List[str]:
        return Config.FORCED_CHANNELS or AdminSystem.load_channels()

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not AdminSystem.is_admin(user_id):
        await update.message.reply_text("❌ عذراً، هذا الأمر مخصص للمشرفين فقط!")
        return
    
    channels = AdminSystem.get_channels()
    channels_count = len(channels)
    channels_list = "\n".join([f"• @{ch}" for ch in channels]) if channels else "لا توجد قنوات"
    
    message = (
        "👑 **لوحة تحكم المشرف**\n\n"
        f"📢 **قنوات الاشتراك الإجباري:** ({channels_count})\n"
        f"{channels_list}\n\n"
        "🔧 **الأوامر المتاحة:**"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة قناة", callback_data="admin_add_channel")],
        [InlineKeyboardButton("➖ حذف قناة", callback_data="admin_remove_channel")],
        [InlineKeyboardButton("📢 إرسال إشعار", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🧹 تنظيف الملفات", callback_data="admin_cleanup")],
        [InlineKeyboardButton("📊 إحصائيات", callback_data="admin_stats")],
        [InlineKeyboardButton("❌ إغلاق", callback_data="admin_close")]
    ])
    
    await update.message.reply_text(message, reply_markup=keyboard, parse_mode="Markdown")

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not AdminSystem.is_admin(user_id):
        await query.edit_message_text("❌ عذراً، هذا الأمر مخصص للمشرفين فقط!")
        return
    
    action = query.data
    if action == "admin_close":
        await query.edit_message_text("✅ تم إغلاق لوحة التحكم")
        return
    await query.edit_message_text("✅ تم تنفيذ الأمر بنجاح!")

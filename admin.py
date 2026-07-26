# admin.py - إضافة دوال إدارة القنوات
import json
from pathlib import Path
from typing import List
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from config import Config
from utils import logger

CHANNELS_FILE = Path(Config.TEMP_DIR).parent / "channels.json"

class AdminSystem:
    @staticmethod
    def load_channels() -> List[str]:
        try:
            if CHANNELS_FILE.exists():
                with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            return []
        except Exception:
            return []
    
    @staticmethod
    def save_channels(channels: List[str]) -> bool:
        try:
            with open(CHANNELS_FILE, "w", encoding="utf-8") as f:
                json.dump(channels, f, ensure_ascii=False, indent=2)
            Config.FORCED_CHANNELS = channels
            return True
        except Exception:
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
        await update.message.reply_text("❌ هذا الأمر مخصص للمشرفين فقط!")
        return
    
    channels = AdminSystem.get_channels()
    channels_list = "\n".join([f"• @{ch}" for ch in channels]) if channels else "لا توجد قنوات"
    
    message = (
        "👑 **لوحة تحكم المشرف**\n\n"
        f"📢 **قنوات الاشتراك الإجباري:**\n{channels_list}\n\n"
        "🔧 الأوامر المتاحة:"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة قناة", callback_data="admin_add_channel")],
        [InlineKeyboardButton("➖ حذف قناة", callback_data="admin_remove_channel")],
        [InlineKeyboardButton("📋 عرض القنوات", callback_data="admin_list_channels")],
        [InlineKeyboardButton("❌ إغلاق", callback_data="admin_close")]
    ])
    
    await update.message.reply_text(message, reply_markup=keyboard, parse_mode="Markdown")

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    
    if not AdminSystem.is_admin(user_id):
        await query.edit_message_text("❌ غير مصرح!")
        return
    
    action = query.data
    
    if action == "admin_close":
        await query.edit_message_text("✅ تم الإغلاق")
        return
    
    elif action == "admin_list_channels":
        channels = AdminSystem.get_channels()
        if channels:
            text = "📋 **قائمة القنوات:**\n\n" + "\n".join([f"• @{ch}" for ch in channels])
        else:
            text = "📭 لا توجد قنوات مسجلة"
        await query.edit_message_text(text, parse_mode="Markdown")
        return
    
    elif action == "admin_add_channel":
        await query.edit_message_text(
            "📝 **إضافة قناة جديدة**\n\n"
            "أرسل معرف القناة:\n"
            "مثال: `@bexo50`\n\n"
            "لإلغاء العملية أرسل /cancel",
            parse_mode="Markdown"
        )
        return "ADD_CHANNEL"
    
    elif action == "admin_remove_channel":
        channels = AdminSystem.get_channels()
        if not channels:
            await query.edit_message_text("📭 لا توجد قنوات لحذفها!")
            return
        
        keyboard = []
        for channel in channels:
            keyboard.append([InlineKeyboardButton(
                f"❌ حذف @{channel}",
                callback_data=f"remove_{channel}"
            )])
        keyboard.append([InlineKeyboardButton("⬅️ رجوع", callback_data="admin_back")])
        
        await query.edit_message_text(
            "🗑️ **اختر القناة لحذفها:**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return
    
    elif action.startswith("remove_"):
        channel = action.replace("remove_", "")
        channels = AdminSystem.get_channels()
        if channel in channels:
            channels.remove(channel)
            AdminSystem.save_channels(channels)
            await query.edit_message_text(f"✅ تم حذف القناة @{channel}!")
        else:
            await query.edit_message_text("❌ القناة غير موجودة!")
        return
    
    elif action == "admin_back":
        await admin_panel(update, context)
        return

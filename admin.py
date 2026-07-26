# admin.py
import json
from pathlib import Path
from typing import List, Optional
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from config import Config
from utils import logger

CHANNELS_FILE = Path(Config.TEMP_DIR).parent / "channels.json"
ADD_CHANNEL = 10

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
    def get_all_channels() -> List[str]:
        """الحصول على جميع القنوات (الثابتة + الإضافية)"""
        channels = [Config.FORCED_CHANNEL] if Config.FORCED_CHANNEL else []
        channels += Config.FORCED_CHANNELS
        return list(dict.fromkeys(channels))

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not AdminSystem.is_admin(user_id):
        await update.message.reply_text("❌ هذا الأمر مخصص للمشرفين فقط!")
        return
    
    # ✅ عرض القنوات (الثابتة + الإضافية)
    all_channels = AdminSystem.get_all_channels()
    forced_channel = Config.FORCED_CHANNEL
    
    channels_list = ""
    if forced_channel:
        channels_list += f"• @{forced_channel} ✅ (ثابتة)\n"
    
    extra_channels = AdminSystem.load_channels()
    for ch in extra_channels:
        channels_list += f"• @{ch}\n"
    
    if not channels_list:
        channels_list = "لا توجد قنوات"
    
    message = (
        "👑 **لوحة تحكم المشرف**\n\n"
        f"📢 **قنوات الاشتراك الإجباري:**\n{channels_list}\n\n"
        f"🔒 القناة الثابتة: @{forced_channel if forced_channel else 'لا توجد'}\n\n"
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
        return ConversationHandler.END
    
    elif action == "admin_list_channels":
        all_channels = AdminSystem.get_all_channels()
        forced_channel = Config.FORCED_CHANNEL
        
        text = "📋 **قائمة القنوات:**\n\n"
        if forced_channel:
            text += f"✅ @{forced_channel} (ثابتة)\n"
        
        extra = AdminSystem.load_channels()
        for ch in extra:
            text += f"• @{ch}\n"
        
        if not all_channels:
            text = "📭 لا توجد قنوات مسجلة"
        
        await query.edit_message_text(text, parse_mode="Markdown")
        return
    
    elif action == "admin_add_channel":
        context.user_data['admin_action'] = 'add_channel'
        
        await query.edit_message_text(
            "📝 **إضافة قناة جديدة**\n\n"
            "أرسل معرف القناة بالصيغة التالية:\n"
            "مثال: `@bexo50`\n\n"
            "📌 ملاحظة: القناة @bexo50 ثابتة ولا يمكن حذفها\n\n"
            "لإلغاء العملية أرسل /cancel",
            parse_mode="Markdown"
        )
        return ADD_CHANNEL
    
    elif action == "admin_remove_channel":
        extra_channels = AdminSystem.load_channels()
        forced_channel = Config.FORCED_CHANNEL
        
        if not extra_channels:
            await query.edit_message_text("📭 لا توجد قنوات إضافية لحذفها!\n\nالقناة الثابتة لا يمكن حذفها.")
            return
        
        keyboard = []
        for channel in extra_channels:
            keyboard.append([InlineKeyboardButton(
                f"❌ حذف @{channel}",
                callback_data=f"remove_{channel}"
            )])
        keyboard.append([InlineKeyboardButton("⬅️ رجوع", callback_data="admin_back")])
        
        await query.edit_message_text(
            "🗑️ **اختر القناة لحذفها:**\n\n"
            f"🔒 القناة الثابتة @{forced_channel} لا يمكن حذفها",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return
    
    elif action.startswith("remove_"):
        channel = action.replace("remove_", "")
        
        # ✅ منع حذف القناة الثابتة
        if channel == Config.FORCED_CHANNEL:
            await query.edit_message_text(
                f"❌ لا يمكن حذف القناة الثابتة @{channel}!\n"
                "هذه القناة مضبوطة بشكل دائم."
            )
            return
        
        extra_channels = AdminSystem.load_channels()
        if channel in extra_channels:
            extra_channels.remove(channel)
            AdminSystem.save_channels(extra_channels)
            await query.edit_message_text(f"✅ تم حذف القناة @{channel}!")
        else:
            await query.edit_message_text("❌ القناة غير موجودة!")
        return
    
    elif action == "admin_back":
        await admin_panel(update, context)
        return

async def add_channel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج إضافة قناة جديدة"""
    user_id = update.effective_user.id
    
    if not AdminSystem.is_admin(user_id):
        await update.message.reply_text("❌ غير مصرح!")
        return ConversationHandler.END
    
    channel_input = update.message.text.strip()
    
    if channel_input == "/cancel":
        await update.message.reply_text("✅ تم إلغاء العملية", reply_markup=MAIN_MENU)
        return ConversationHandler.END
    
    # ✅ تنظيف معرف القناة
    channel = channel_input.replace("@", "").strip()
    
    if not channel:
        await update.message.reply_text(
            "❌ معرف القناة غير صالح!\n"
            "أرسل معرف القناة بالصيغة: `@username`\n"
            "مثال: `@bexo50`",
            parse_mode="Markdown"
        )
        return ADD_CHANNEL
    
    # ✅ منع إضافة القناة الثابتة مرة أخرى
    if channel == Config.FORCED_CHANNEL:
        await update.message.reply_text(
            f"⚠️ القناة @{channel} هي القناة الثابتة!\n"
            "تم إضافتها بشكل دائم ولا تحتاج لإضافتها مرة أخرى."
        )
        return ADD_CHANNEL
    
    try:
        # ✅ التحقق من وجود القناة
        chat = await context.bot.get_chat(f"@{channel}")
        
        # ✅ التأكد من أن البوت مشرف في القناة
        try:
            bot_member = await context.bot.get_chat_member(
                chat_id=f"@{channel}",
                user_id=context.bot.id
            )
            
            if bot_member.status not in ["administrator", "creator"]:
                await update.message.reply_text(
                    f"⚠️ البوت ليس مشرفاً في القناة @{channel}!\n"
                    "يرجى إضافة البوت كمشرف في القناة ثم حاول مرة أخرى."
                )
                return ADD_CHANNEL
                
        except Exception as e:
            await update.message.reply_text(
                f"⚠️ لا يمكن التحقق من صلاحيات البوت في القناة @{channel}!\n"
                "تأكد من أن البوت مشرف في القناة."
            )
            return ADD_CHANNEL
        
        # ✅ إضافة القناة
        extra_channels = AdminSystem.load_channels()
        if channel in extra_channels:
            await update.message.reply_text(f"⚠️ القناة @{channel} موجودة بالفعل!")
        else:
            extra_channels.append(channel)
            AdminSystem.save_channels(extra_channels)
            await update.message.reply_text(
                f"✅ تم إضافة القناة @{channel} بنجاح!\n\n"
                f"📢 سيُطلب من المستخدمين الاشتراك في:\n"
                f"• @{Config.FORCED_CHANNEL} (ثابتة)\n"
                f"• @{channel} (جديدة)"
            )
        
        await admin_panel(update, context)
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"خطأ في إضافة القناة: {e}")
        await update.message.reply_text(
            f"❌ حدث خطأ: {str(e)[:200]}\n\n"
            "تأكد من أن:\n"
            "1️⃣ معرف القناة صحيح\n"
            "2️⃣ البوت مشرف في القناة\n"
            "3️⃣ القناة عامة (Public)"
        )
        return ADD_CHANNEL

# ✅ استيراد MAIN_MENU من keyboards
from keyboards import MAIN_MENU

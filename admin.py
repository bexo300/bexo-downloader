# admin.py - نظام التحكم الكامل للمشرفين
import os
import json
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from config import Config
from utils import logger, format_size, safe_remove

# ملف لحفظ بيانات القنوات
CHANNELS_FILE = Path(Config.TEMP_DIR).parent / "channels.json"

# حالات المحادثة للمشرف
ADMIN_MENU, ADD_CHANNEL, REMOVE_CHANNEL, BROADCAST, STATS, CLEANUP = range(6)

class AdminSystem:
    """نظام إدارة المشرفين"""
    
    @staticmethod
    def load_channels():
        """تحميل قائمة القنوات من الملف"""
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
        """حفظ قائمة القنوات"""
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
        """التحقق من صلاحيات المشرف"""
        return user_id in Config.ADMINS
    
    @staticmethod
    def get_channels() -> List[str]:
        """الحصول على قائمة القنوات"""
        return Config.FORCED_CHANNELS or AdminSystem.load_channels()

# ============= دوال التحقق من الاشتراك المتقدمة =============

async def check_all_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """التحقق من اشتراك المستخدم في جميع القنوات"""
    user_id = update.effective_user.id
    channels = AdminSystem.get_channels()
    
    # إذا كان المستخدم مشرف، تخطي التحقق
    if AdminSystem.is_admin(user_id):
        return True
    
    if not channels:
        return True
    
    unsubscribed = []
    
    for channel in channels:
        # تنظيف اسم القناة
        channel_name = channel.strip()
        if channel_name.startswith("@"):
            channel_name = channel_name[1:]
        
        try:
            chat_member = await context.bot.get_chat_member(
                chat_id=f"@{channel_name}",
                user_id=user_id
            )
            
            status = chat_member.status
            if status not in ["member", "administrator", "creator"]:
                unsubscribed.append(channel_name)
                
        except Exception as e:
            logger.error(f"خطأ في التحقق من قناة {channel_name}: {e}")
            unsubscribed.append(channel_name)
    
    if unsubscribed:
        await send_subscription_required(update, context, unsubscribed)
        return False
    
    return True

async def send_subscription_required(update: Update, context: ContextTypes.DEFAULT_TYPE, channels: List[str]):
    """إرسال رسالة الاشتراك الإجباري مع جميع القنوات"""
    keyboard = []
    
    for channel in channels:
        channel_name = channel.strip()
        if channel_name.startswith("@"):
            channel_name = channel_name[1:]
        keyboard.append([InlineKeyboardButton(
            f"📢 اشترك في @{channel_name}",
            url=f"https://t.me/{channel_name}"
        )])
    
    keyboard.append([InlineKeyboardButton(
        "✅ تحقق من الاشتراك",
        callback_data="check_all_subscriptions"
    )])
    
    inline_keyboard = InlineKeyboardMarkup(keyboard)
    
    channels_text = "\n".join([f"• @{ch}" for ch in channels])
    
    message_text = (
        "🔒 **يجب الاشتراك في القنوات التالية لاستخدام البوت:**\n\n"
        f"{channels_text}\n\n"
        "📌 **الخطوات:**\n"
        "1️⃣ اضغط على أزرار الاشتراك\n"
        "2️⃣ اشترك في جميع القنوات\n"
        "3️⃣ اضغط على 'تحقق من الاشتراك'\n\n"
        "✅ بعد الاشتراك، ستتمكن من استخدام جميع ميزات البوت!"
    )
    
    await update.message.reply_text(
        message_text,
        reply_markup=inline_keyboard,
        parse_mode="Markdown"
    )

# ============= لوحة تحكم المشرف =============

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض لوحة تحكم المشرف"""
    user_id = update.effective_user.id
    
    if not AdminSystem.is_admin(user_id):
        await update.message.reply_text("❌ عذراً، هذا الأمر مخصص للمشرفين فقط!")
        return
    
    channels = AdminSystem.get_channels()
    channels_count = len(channels)
    channels_list = "\n".join([f"• @{ch}" for ch in channels]) if channels else "لا توجد قنوات"
    
    # إحصائيات سريعة
    stats = await get_bot_stats(context)
    
    message = (
        "👑 **لوحة تحكم المشرف**\n\n"
        f"📊 **الإحصائيات:**\n"
        f"• المستخدمين النشطين: {stats['active_users']}\n"
        f"• الملفات المؤقتة: {stats['temp_files']}\n"
        f"• حجم الملفات المؤقتة: {stats['temp_size']}\n\n"
        f"📢 **قنوات الاشتراك الإجباري:** ({channels_count})\n"
        f"{channels_list}\n\n"
        "🔧 **الأوامر المتاحة:**"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة قناة", callback_data="admin_add_channel")],
        [InlineKeyboardButton("➖ حذف قناة", callback_data="admin_remove_channel")],
        [InlineKeyboardButton("📢 إرسال إشعار للجميع", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🧹 تنظيف الملفات المؤقتة", callback_data="admin_cleanup")],
        [InlineKeyboardButton("📊 عرض إحصائيات مفصلة", callback_data="admin_stats")],
        [InlineKeyboardButton("🔄 تحديث القوائم", callback_data="admin_refresh")],
        [InlineKeyboardButton("❌ إغلاق اللوحة", callback_data="admin_close")]
    ])
    
    await update.message.reply_text(
        message,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج أزرار لوحة التحكم"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if not AdminSystem.is_admin(user_id):
        await query.edit_message_text("❌ عذراً، هذا الأمر مخصص للمشرفين فقط!")
        return
    
    action = query.data
    
    if action == "admin_add_channel":
        await query.edit_message_text(
            "📝 **إضافة قناة جديدة**\n\n"
            "أرسل معرف القناة بالصيغة التالية:\n"
            "`@username` أو `-1001234567890`\n\n"
            "📌 مثال: `@bexo50`\n\n"
            "لإلغاء العملية أرسل /cancel",
            parse_mode="Markdown"
        )
        return ADD_CHANNEL
    
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
    
    elif action == "admin_broadcast":
        await query.edit_message_text(
            "📢 **إرسال إشعار للجميع**\n\n"
            "أرسل الرسالة التي تريد نشرها لجميع المستخدمين.\n\n"
            "لإلغاء العملية أرسل /cancel",
            parse_mode="Markdown"
        )
        return BROADCAST
    
    elif action == "admin_cleanup":
        await query.edit_message_text("🧹 جاري تنظيف الملفات المؤقتة...")
        cleaned = await cleanup_temp_files(context)
        await query.edit_message_text(
            f"🧹 **تم التنظيف بنجاح!**\n\n"
            f"🗑️ تم حذف {cleaned} ملف مؤقت.",
            parse_mode="Markdown"
        )
        return
    
    elif action == "admin_stats":
        stats = await get_bot_stats(context)
        message = (
            "📊 **إحصائيات مفصلة**\n\n"
            f"👤 المستخدمين النشطين: {stats['active_users']}\n"
            f"📁 الملفات المؤقتة: {stats['temp_files']}\n"
            f"💾 حجم الملفات: {stats['temp_size']}\n"
            f"📢 القنوات المسجلة: {len(AdminSystem.get_channels())}\n"
            f"🕒 وقت التشغيل: {stats['uptime']}\n\n"
            f"📂 مجلد الملفات: {Config.TEMP_DIR}"
        )
        await query.edit_message_text(message, parse_mode="Markdown")
        return
    
    elif action == "admin_refresh":
        Config.FORCED_CHANNELS = AdminSystem.load_channels()
        await query.edit_message_text("✅ تم تحديث القوائم بنجاح!")
        return
    
    elif action.startswith("remove_"):
        channel = action.replace("remove_", "")
        channels = AdminSystem.get_channels()
        if channel in channels:
            channels.remove(channel)
            AdminSystem.save_channels(channels)
            await query.edit_message_text(f"✅ تم حذف القناة @{channel} بنجاح!")
        else:
            await query.edit_message_text("❌ القناة غير موجودة!")
        return
    
    elif action == "admin_back":
        await admin_panel(update, context)
        return
    
    elif action == "admin_close":
        await query.edit_message_text("✅ تم إغلاق لوحة التحكم")
        return

async def add_channel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج إضافة قناة"""
    user_id = update.effective_user.id
    channel_input = update.message.text.strip()
    
    if channel_input == "/cancel":
        await update.message.reply_text("✅ تم إلغاء العملية")
        return ConversationHandler.END
    
    # تنظيف المدخلات
    channel = channel_input.replace("@", "").strip()
    
    # التحقق من صحة القناة
    try:
        # محاولة جلب معلومات القناة للتحقق
        chat = await context.bot.get_chat(f"@{channel}")
        if chat.type not in ["channel", "supergroup"]:
            await update.message.reply_text("❌ هذا ليس معرف قناة صحيح! حاول مرة أخرى.")
            return ADD_CHANNEL
        
        # إضافة القناة
        channels = AdminSystem.get_channels()
        if channel in channels:
            await update.message.reply_text(f"⚠️ القناة @{channel} موجودة بالفعل!")
        else:
            channels.append(channel)
            AdminSystem.save_channels(channels)
            await update.message.reply_text(
                f"✅ تم إضافة القناة @{channel} بنجاح!\n"
                f"📢 سيُطلب من المستخدمين الاشتراك فيها."
            )
        
    except Exception as e:
        logger.error(f"خطأ في إضافة القناة: {e}")
        await update.message.reply_text(
            f"❌ حدث خطأ: {str(e)}\n"
            "تأكد من أن المعرف صحيح وأن البوت مشرف في القناة."
        )
        return ADD_CHANNEL
    
    return ConversationHandler.END

async def broadcast_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج إرسال الإشعارات"""
    user_id = update.effective_user.id
    message_text = update.message.text
    
    if message_text == "/cancel":
        await update.message.reply_text("✅ تم إلغاء الإشعار")
        return ConversationHandler.END
    
    # هنا يمكن جلب قائمة المستخدمين من قاعدة بيانات
    # حالياً نرسل للمستخدم الحالي فقط كتجربة
    await update.message.reply_text(
        "📢 **تم إرسال الإشعار:**\n\n"
        f"{message_text}\n\n"
        "✅ سيتم إرساله لجميع المستخدمين (تطوير مستقبلي)",
        parse_mode="Markdown"
    )
    
    return ConversationHandler.END

async def get_bot_stats(context: ContextTypes.DEFAULT_TYPE) -> Dict[str, Any]:
    """جلب إحصائيات البوت"""
    # عدد الملفات المؤقتة
    temp_files = 0
    temp_size = 0
    
    temp_dir = Path(Config.TEMP_DIR)
    if temp_dir.exists():
        for file in temp_dir.iterdir():
            if file.is_file():
                temp_files += 1
                temp_size += file.stat().st_size
    
    return {
        "active_users": len(context.bot_data.get("active_users", set())),
        "temp_files": temp_files,
        "temp_size": format_size(temp_size),
        "uptime": "قيد التشغيل"  # يمكن إضافة وقت التشغيل
    }

async def cleanup_temp_files(context: ContextTypes.DEFAULT_TYPE) -> int:
    """تنظيف الملفات المؤقتة"""
    count = 0
    temp_dir = Path(Config.TEMP_DIR)
    if temp_dir.exists():
        for file in temp_dir.iterdir():
            if file.is_file():
                try:
                    file.unlink()
                    count += 1
                except:
                    pass
    return count

# ============= دالة التحقق الموحدة =============

async def check_subscription_required(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """دالة موحدة للتحقق من الاشتراك في جميع القنوات"""
    user_id = update.effective_user.id
    
    # إذا كان المشرف، تخطي
    if AdminSystem.is_admin(user_id):
        return True
    
    # التحقق من الاشتراك
    return await check_all_subscriptions(update, context)

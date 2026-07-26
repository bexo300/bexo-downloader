# main.py - مع إضافة نظام المشرفين
import os
import asyncio
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler, CallbackQueryHandler
)
from config import Config
from utils import (
    logger, set_user_busy, is_user_busy, clean_old_files, 
    validate_page_range, format_size, sanitize_filename, 
    safe_remove, ensure_dir
)
from pdf_engine import PDFEngine
from keyboards import MAIN_MENU, ACTION_MENU, CANCEL_BTN
from admin import (
    AdminSystem, admin_panel, admin_callback_handler,
    add_channel_handler, broadcast_handler, check_subscription_required,
    ADMIN_MENU, ADD_CHANNEL, REMOVE_CHANNEL, BROADCAST, STATS, CLEANUP
)

Config.ensure_dirs()

@dataclass
class Session:
    files: List[str] = field(default_factory=list)
    action: Optional[str] = None
    val1: Optional[str] = None
    custom_name: Optional[str] = None
    expecting_name: bool = False
    expecting_data: bool = False
    last_active: float = field(default_factory=time.time)
    operation_completed: bool = False
    checked_subscription: bool = False

user_sessions: Dict[int, Session] = {}
SELECT_ACTION, WAIT_FILE, WAIT_DATA, WAIT_NAME = range(4)

# ============= دوال البوت الرئيسية =============

async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"خطأ عام: {context.error}", exc_info=True)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ حدث خطأ غير متوقع.\nالرجاء المحاولة مرة أخرى.",
                reply_markup=MAIN_MENU
            )
        except Exception:
            pass

async def cleanup_task(context: ContextTypes.DEFAULT_TYPE):
    clean_old_files()
    now = time.time()
    for uid, session in list(user_sessions.items()):
        if now - session.last_active > Config.MAX_SESSION_TIME:
            for file_path in session.files:
                safe_remove(file_path)
            user_sessions.pop(uid, None)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء البوت مع التحقق من الاشتراك"""
    uid = update.effective_user.id
    
    # ✅ التحقق من الاشتراك الإجباري
    if not await check_subscription_required(update, context):
        return SELECT_ACTION
    
    user_sessions[uid] = Session(checked_subscription=True)
    
    welcome_text = (
        "👋 مرحباً بك في بوت PDF الاحترافي!\n\n"
        "📚 يمكنك تنفيذ العديد من المهام على ملفات PDF:\n"
        "• دمج ملفات PDF متعددة\n"
        "• تحويل الصور إلى PDF\n"
        "• استخراج الصور من PDF\n"
        "• ترقيم الصفحات\n"
        "• تقسيم وحذف الصفحات\n"
        "• ضغط الملفات\n"
        "• إضافة علامات مائية\n"
        "• حماية الملفات بكلمة مرور\n\n"
        "اختر الأداة التي تريدها من القائمة أدناه 🚀"
    )
    
    await update.message.reply_text(welcome_text, reply_markup=MAIN_MENU)
    return SELECT_ACTION

# ✅ إضافة أمر لوحة التحكم
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /admin - لوحة تحكم المشرف"""
    await admin_panel(update, context)

async def choose_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اختيار العملية مع التحقق من الاشتراك"""
    uid = update.effective_user.id
    
    if not await check_subscription_required(update, context):
        return SELECT_ACTION
    
    # التحقق من عمليات المشرف الخاصة
    if update.message.text == "👑 لوحة التحكم":
        return await admin_command(update, context)
    
    if is_user_busy(uid):
        await update.message.reply_text(
            "⏳ لديك عملية جارية حالياً، انتظر انتهائها أولاً.",
            reply_markup=MAIN_MENU
        )
        return SELECT_ACTION
    
    # ... باقي الكود كما هو

# ============= باقي الدوال كما هي =============

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء العملية"""
    uid = update.effective_user.id
    if uid in user_sessions:
        session = user_sessions[uid]
        for file_path in session.files:
            safe_remove(file_path)
        user_sessions.pop(uid, None)
    
    await update.message.reply_text("✅ تم إلغاء العملية", reply_markup=MAIN_MENU)
    return SELECT_ACTION

def main():
    """الوظيفة الرئيسية لتشغيل البوت"""
    if not Config.BOT_TOKEN:
        logger.error("❌ BOT_TOKEN غير موجود في ملف .env")
        return
    
    # تحميل القنوات المحفوظة
    Config.FORCED_CHANNELS = AdminSystem.load_channels()
    
    app = ApplicationBuilder().token(Config.BOT_TOKEN).build()
    
    # ✅ معالج التحقق من الاشتراك
    app.add_handler(CallbackQueryHandler(
        admin_callback_handler, 
        pattern="^(admin_|remove_).*"
    ))
    
    # ✅ معالج التحقق من الاشتراك المتعدد
    app.add_handler(CallbackQueryHandler(
        lambda u, c: check_subscription_required(u, c),
        pattern="check_all_subscriptions"
    ))
    
    # ✅ أمر لوحة التحكم
    app.add_handler(CommandHandler("admin", admin_command))
    
    # ✅ محادثة إضافة قناة
    add_channel_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(lambda u, c: ADD_CHANNEL, pattern="admin_add_channel")],
        states={
            ADD_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_channel_handler)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(add_channel_conv)
    
    # ✅ محادثة الإشعارات
    broadcast_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(lambda u, c: BROADCAST, pattern="admin_broadcast")],
        states={
            BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_handler)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(broadcast_conv)
    
    # ✅ محادثة البوت الرئيسية
    conversation_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("cancel", cancel)
        ],
        states={
            SELECT_ACTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, choose_action)
            ],
            WAIT_FILE: [
                MessageHandler(filters.ALL & ~filters.COMMAND, receive_files)
            ],
            WAIT_DATA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_data)
            ],
            WAIT_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)
            ]
        },
        fallbacks=[
            CommandHandler("start", start),
            CommandHandler("cancel", cancel)
        ],
        per_user=True
    )
    
    app.add_handler(conversation_handler)
    app.add_error_handler(global_error_handler)
    
    app.job_queue.run_repeating(cleanup_task, interval=Config.CLEANUP_INTERVAL, first=10)
    
    logger.info("🚀 بوت PDF الاحترافي يعمل الآن!")
    logger.info(f"📁 مجلد الملفات المؤقتة: {Config.TEMP_DIR}")
    logger.info(f"👑 عدد المشرفين: {len(Config.ADMINS)}")
    logger.info(f"📢 عدد قنوات الاشتراك: {len(Config.FORCED_CHANNELS)}")
    
    try:
        app.run_polling(drop_pending_updates=True)
    except Exception as e:
        logger.error(f"خطأ في تشغيل البوت: {e}", exc_info=True)

if __name__ == "__main__":
    main()

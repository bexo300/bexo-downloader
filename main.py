import os
import asyncio
import tempfile
import time  # ✅ مهم جداً
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, List
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler, CallbackQueryHandler
)
from config import Config
from utils import logger, set_user_busy, is_user_busy, clean_old_files, validate_page_range, format_size
from pdf_engine import PDFEngine
from keyboards import MAIN_MENU, ACTION_MENU, CANCEL_BTN

Config.ensure_dirs()

@dataclass
class Session:
    files: List[str] = field(default_factory=list)
    action: Optional[str] = None
    val1: Optional[str] = None
    custom_name: Optional[str] = None
    expecting_name: bool = False
    # ✅ نستخدم default_factory بدلاً من القيمة مباشرة
    last_active: float = field(default_factory=time.time)


user_sessions: dict[int, Session] = {}
SELECT_ACTION, WAIT_FILE, WAIT_DATA, WAIT_NAME = range(4)

# معالج أخطاء عام
async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"خطأ عام: {context.error}", exc_info=True)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text("❌ حدث خطأ غير متوقع، جرب مرة أخرى أو تواصل مع المطور.")

# تنظيف دوري
async def cleanup_task(context: ContextTypes.DEFAULT_TYPE):
    clean_old_files()
    now = time.time()
    for uid, s in list(user_sessions.items()):
        if now - s.last_active > Config.MAX_SESSION_TIME:
            for f in s.files: os.path.exists(f) and os.remove(f)
            user_sessions.pop(uid, None)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_sessions[uid] = Session()
    await update.message.reply_text(
        "👋 مرحباً بك في بوت PDF الاحترافي!\n"
        "اختر الأداة التي تريدها من القائمة أدناه، والبوت سيقوم بالباقي 🚀",
        reply_markup=MAIN_MENU
    )
    return SELECT_ACTION

async def choose_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    act = update.message.text
    if is_user_busy(uid):
        await update.message.reply_text("⏳ لديك عملية جارية حالياً، انتظر انتهائها أولاً.")
        return SELECT_ACTION
    s = user_sessions[uid]
    s.action = act
    s.last_active = time.time()
    prompts = {
        "📎 دمج PDF": "أرسل ملفات PDF واحدة تلو الأخرى، ثم اضغط إنهاء",
        "🔢 ترقيم الصفحات": "أرسل ملف PDF لإضافة أرقام الصفحات",
        "📉 ضغط": "أرسل ملف PDF لتقليل حجمه",
        "💧 علامة مائية": "أرسل ملف PDF ثم نص العلامة المائية",
        "🔒 حماية": "أرسل ملف PDF ثم كلمة المرور",
        "🖼️ صور لـ PDF": "أرسل الصور ثم إنهاء"
    }
    await update.message.reply_text(prompts.get(act, "أرسل الملف المطلوب"), reply_markup=ACTION_MENU)
    return WAIT_FILE

async def receive_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    s = user_sessions.get(uid)
    if not s: return await start(update, context)
    s.last_active = time.time()

    if update.message.text == "❌ إلغاء":
        for f in s.files: os.path.exists(f) and os.remove(f)
        user_sessions.pop(uid)
        await update.message.reply_text("✅ تم إلغاء العملية", reply_markup=MAIN_MENU)
        return SELECT_ACTION

    if update.message.text == "✅ إنهاء العملية":
        await update.message.reply_text("📝 أرسل اسم الملف الجديد أو أرسل فارغاً للاسم الافتراضي:")
        return WAIT_NAME

    if update.message.document:
        doc = update.message.document
        f = await context.bot.get_file(doc.file_id)
        path = os.path.join(Config.TEMP_DIR, f"f_{uid}_{len(s.files)}_{os.urandom(2).hex()}.pdf")
        await f.download_to_drive(path)
        s.files.append(path)
        await update.message.reply_text(f"✅ تم استلام | العدد: {len(s.files)}", reply_markup=ACTION_MENU)
    return WAIT_FILE

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    s = user_sessions.get(uid)
    if not s or not s.files: return await start(update, context)
    s.custom_name = update.message.text.strip() or None
    return await process_work(update, context, s)

async def process_work(update: Update, context: ContextTypes.DEFAULT_TYPE, s: Session):
    uid = update.effective_user.id
    set_user_busy(uid, True)
    try:
        act = s.action
        final_name = s.custom_name or {
            "📎 دمج PDF": "ملفات_مدمجة.pdf", "🔢 ترقيم الصفحات": "ملف_مرقم.pdf",
            "📉 ضغط": "ملف_مضغوط.pdf", "💧 علامة مائية": "ملف_بعلامة.pdf",
            "🔒 حماية": "ملف_محمي.pdf", "🖼️ صور لـ PDF": "صور_محولة.pdf"
        }.get(act, "ملف_جديد.pdf")
        if not final_name.lower().endswith((".pdf", ".zip")): final_name += ".pdf"

        await update.message.reply_text("⏳ جاري المعالجة...")
        result_path = None
        extra = ""

        if act == "📎 دمج PDF":
            result_path = await asyncio.to_thread(PDFEngine.merge, s.files)
        elif act == "🔢 ترقيم الصفحات":
            result_path = await asyncio.to_thread(PDFEngine.add_page_numbers, s.files[0])
        elif act == "📉 ضغط":
            result_path, bef, aft = await asyncio.to_thread(PDFEngine.compress, s.files[0])
            extra = f"\n📊 الحجم: {format_size(bef)} → {format_size(aft)}\n✅ تم التخفيض بنسبة {round((1-aft/bef)*100)}%"
        elif act == "💧 علامة مائية":
            result_path = await asyncio.to_thread(PDFEngine.add_watermark, s.files[0], s.val1 or "نص تجريبي")
        elif act == "🔒 حماية":
            result_path = await asyncio.to_thread(PDFEngine.encrypt, s.files[0], s.val1 or "1234")

        if result_path and os.path.exists(result_path):
            with open(result_path, "rb") as f:
                await update.message.reply_document(f, filename=final_name, caption=f"✅ تمت العملية بنجاح{extra}", reply_markup=MAIN_MENU)
            os.remove(result_path)
    except Exception as e:
        logger.error(f"خطأ في المعالجة: {e}", exc_info=True)
        await update.message.reply_text(f"❌ خطأ: {str(e)[:100]}", reply_markup=MAIN_MENU)
    finally:
        set_user_busy(uid, False)
        for f in s.files: os.path.exists(f) and os.remove(f)
        user_sessions.pop(uid, None)
    return SELECT_ACTION

def main():
    app = ApplicationBuilder().token(Config.BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_action)],
            WAIT_FILE: [MessageHandler(filters.ALL & ~filters.COMMAND, receive_files)],
            WAIT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)]
        },
        fallbacks=[CommandHandler("start", start)],
        per_user=True
    )
    app.add_handler(conv)
    app.add_error_handler(global_error_handler)
    app.job_queue.run_repeating(cleanup_task, interval=Config.CLEANUP_INTERVAL)
    logger.info("🚀 بوت PDF الاحترافي يعمل الآن!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    import time
    main()

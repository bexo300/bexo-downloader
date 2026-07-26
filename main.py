import os
import asyncio
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler, CallbackQueryHandler
)
from config import Config
from utils import (
    logger, set_user_busy, is_user_busy, clean_old_files, 
    validate_page_range, format_size, sanitize_filename, 
    safe_remove, ensure_dir, ensure_extension  # ✅ إضافة ensure_extension
)
from pdf_engine import PDFEngine
from keyboards import MAIN_MENU, ACTION_MENU, CANCEL_BTN
from admin import AdminSystem, admin_panel, admin_callback_handler
from pypdf import PdfReader

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

async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"خطأ عام: {context.error}", exc_info=True)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text("❌ حدث خطأ غير متوقع، حاول مرة أخرى.", reply_markup=MAIN_MENU)
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
    uid = update.effective_user.id
    user_sessions[uid] = Session()
    welcome_text = "👋 مرحباً بك في بوت PDF الاحترافي!\nاختر الأداة التي تريدها من القائمة أدناه 🚀"
    
    # ✅ عرض زر المشرف فقط للمشرفين
    if AdminSystem.is_admin(uid):
        from keyboards import ADMIN_MENU
        await update.message.reply_text(welcome_text, reply_markup=MAIN_MENU)
        await update.message.reply_text("👑 لوحة التحكم متاحة لك!", reply_markup=ADMIN_MENU)
    else:
        await update.message.reply_text(welcome_text, reply_markup=MAIN_MENU)
    
    return SELECT_ACTION

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await admin_panel(update, context)

async def choose_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    action_text = update.message.text
    
    if action_text == "👑 لوحة التحكم":
        if not AdminSystem.is_admin(uid):
            await update.message.reply_text("❌ عذراً، هذا الأمر مخصص للمشرفين فقط!", reply_markup=MAIN_MENU)
            return SELECT_ACTION
        return await admin_command(update, context)
    
    if is_user_busy(uid):
        await update.message.reply_text("⏳ لديك عملية جارية حالياً، انتظر انتهائها أولاً.", reply_markup=MAIN_MENU)
        return SELECT_ACTION
    
    session = user_sessions.get(uid)
    if not session:
        session = Session()
        user_sessions[uid] = session
    
    session.action = action_text
    session.last_active = time.time()
    
    prompts = {
        "📎 دمج PDF": "📤 أرسل ملفات PDF واحدة تلو الأخرى، ثم اضغط 'إنهاء العملية'",
        "🖼️ صور لـ PDF": "🖼️ أرسل الصور واحدة تلو الأخرى، ثم اضغط 'إنهاء العملية'",
        "📸 استخراج صور": "📄 أرسل ملف PDF لاستخراج الصور منه",
        "🔢 ترقيم الصفحات": "📄 أرسل ملف PDF لإضافة أرقام الصفحات",
        "✂️ تقسيم": "📄 أرسل ملف PDF للتقسيم حسب النطاق (مثال: 1-5,7,10)",
        "🗑️ حذف صفحات": "📄 أرسل ملف PDF لحذف صفحات محددة (مثال: 1,3-5,8)",
        "📉 ضغط": "📄 أرسل ملف PDF لتقليل حجمه",
        #"💧 علامة مائية": "📄 أرسل ملف PDF ثم النص الذي تريد وضعه كعلامة مائية",
        "🔒 حماية": "📄 أرسل ملف PDF ثم كلمة المرور للتشفير",
       # "ℹ️ معلومات": "📄 أرسل ملف PDF لعرض معلوماته",
        #"🧹 مسح الملفات": "🗑️ سيتم حذف جميع ملفاتك المؤقتة"
    }
    
    prompt = prompts.get(action_text, "📤 أرسل الملف المطلوب")
    
    if action_text == "🧹 مسح الملفات":
        return await clean_user_files(update, context)
    
    await update.message.reply_text(prompt, reply_markup=ACTION_MENU)
    return WAIT_FILE

async def clean_user_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    count = 0
    temp_path = Path(Config.TEMP_DIR)
    if temp_path.exists():
        for file_path in temp_path.iterdir():
            if file_path.is_file() and file_path.name.startswith(f"f_{uid}_"):
                if safe_remove(str(file_path)):
                    count += 1
    if uid in user_sessions:
        session = user_sessions[uid]
        for file_path in session.files:
            safe_remove(file_path)
        del user_sessions[uid]
    await update.message.reply_text(f"🧹 تم حذف {count} ملف مؤقت بنجاح!", reply_markup=MAIN_MENU)
    return SELECT_ACTION

async def receive_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    session = user_sessions.get(uid)
    if not session:
        return await start(update, context)
    session.last_active = time.time()

    if update.message.text:
        text = update.message.text
        if text == "❌ إلغاء":
            for file_path in session.files:
                safe_remove(file_path)
            user_sessions.pop(uid, None)
            await update.message.reply_text("✅ تم إلغاء العملية", reply_markup=MAIN_MENU)
            return SELECT_ACTION
        if text == "✅ إنهاء العملية":
            if not session.files:
                await update.message.reply_text("⚠️ لم ترسل أي ملفات بعد!", reply_markup=ACTION_MENU)
                return WAIT_FILE
            
            # ✅ العمليات التي تحتاج بيانات إضافية
            data_actions = ["✂️ تقسيم", "🗑️ حذف صفحات", "💧 علامة مائية", "🔒 حماية"]
            if session.action in data_actions:
                # ✅ رسائل مخصصة حسب العملية
                data_prompts = {
                    "✂️ تقسيم": "📝 أدخل نطاق الصفحات للاستخراج (مثال: 1-5,7,10):",
                    "🗑️ حذف صفحات": "📝 أدخل الصفحات المراد حذفها (مثال: 1,3-5,8):",
                    "💧 علامة مائية": "📝 أرسل النص الذي تريد وضعه كعلامة مائية:",
                    "🔒 حماية": "📝 أدخل كلمة المرور للتشفير (4 أحرف على الأقل):"
                }
                await update.message.reply_text(data_prompts.get(session.action, "✏️ أدخل البيانات المطلوبة:"), reply_markup=CANCEL_BTN)
                session.expecting_data = True
                return WAIT_DATA
            
            await update.message.reply_text("📝 أرسل اسم الملف النهائي (أو 'تخطي' للاسم الافتراضي):", reply_markup=CANCEL_BTN)
            session.expecting_name = True
            return WAIT_NAME
        if session.expecting_data:
            return await receive_data(update, context)

    if update.message.document:
        document = update.message.document
        if document.file_size > Config.MAX_FILE_SIZE:
            await update.message.reply_text(f"❌ حجم الملف كبير جداً! الحد الأقصى {format_size(Config.MAX_FILE_SIZE)}", reply_markup=ACTION_MENU)
            return WAIT_FILE
        if document.mime_type not in Config.ALLOWED_TYPES:
            await update.message.reply_text("❌ نوع الملف غير مدعوم!\nالمدعوم: PDF, JPEG, PNG, WEBP, BMP, TIFF", reply_markup=ACTION_MENU)
            return WAIT_FILE
        if len(session.files) >= Config.MAX_FILES_PER_SESSION:
            await update.message.reply_text(f"❌ وصلت للحد الأقصى ({Config.MAX_FILES_PER_SESSION}) ملفات!", reply_markup=ACTION_MENU)
            return WAIT_FILE
        try:
            file_obj = await context.bot.get_file(document.file_id)
            ext = ".pdf" if document.mime_type == "application/pdf" else ".jpg"
            file_path = Path(Config.TEMP_DIR) / f"f_{uid}_{len(session.files)}_{os.urandom(4).hex()}{ext}"
            await file_obj.download_to_drive(str(file_path))
            session.files.append(str(file_path))
            await update.message.reply_text(f"✅ تم استلام الملف ({len(session.files)}/{Config.MAX_FILES_PER_SESSION})", reply_markup=ACTION_MENU)
        except Exception as e:
            logger.error(f"خطأ في تحميل الملف: {e}")
            await update.message.reply_text("❌ حدث خطأ أثناء تحميل الملف", reply_markup=ACTION_MENU)
    return WAIT_FILE

async def receive_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    session = user_sessions.get(uid)
    if not session:
        return await start(update, context)
    
    if update.message.text == "❌ إلغاء":
        for file_path in session.files:
            safe_remove(file_path)
        user_sessions.pop(uid, None)
        await update.message.reply_text("✅ تم إلغاء العملية", reply_markup=MAIN_MENU)
        return SELECT_ACTION
    
    session.val1 = update.message.text.strip()
    session.expecting_data = False
    
    await update.message.reply_text("📝 أرسل اسم الملف النهائي (أو 'تخطي' للاسم الافتراضي):", reply_markup=CANCEL_BTN)
    session.expecting_name = True
    return WAIT_NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    session = user_sessions.get(uid)
    if not session or not session.files:
        return await start(update, context)
    
    if update.message.text == "❌ إلغاء":
        for file_path in session.files:
            safe_remove(file_path)
        user_sessions.pop(uid, None)
        await update.message.reply_text("✅ تم إلغاء العملية", reply_markup=MAIN_MENU)
        return SELECT_ACTION
    
    name = update.message.text.strip()
    if name.lower() == "تخطي":
        session.custom_name = None
    else:
        session.custom_name = sanitize_filename(name)
    
    session.expecting_name = False
    return await process_work(update, context, session)

async def process_work(update: Update, context: ContextTypes.DEFAULT_TYPE, session: Session):
    uid = update.effective_user.id
    set_user_busy(uid, True)
    try:
        action = session.action
        result_path = None
        extra_info = ""
        
        # الأسماء الافتراضية
        default_names = {
            "📎 دمج PDF": "ملفات_مدمجة.pdf",
            "🖼️ صور لـ PDF": "صور_محولة.pdf",
            "📸 استخراج صور": "صور_مستخرجة.zip",
            "🔢 ترقيم الصفحات": "ملف_مرقم.pdf",
            "📉 ضغط": "ملف_مضغوط.pdf",
            "💧 علامة مائية": "ملف_بعلامة.pdf",
            "🔒 حماية": "ملف_محمي.pdf",
            "✂️ تقسيم": "ملف_مقسم.pdf",
            "🗑️ حذف صفحات": "ملف_معدل.pdf",
            "🔓 إزالة الحماية": "ملف_غير_محمي.pdf"
        }
        
        # ✅ معالجة اسم الملف مع إضافة الامتداد التلقائي
        if session.custom_name:
            final_name = session.custom_name
            # ✅ إضافة الامتداد إذا كان مفقوداً
            if not any(final_name.lower().endswith(ext) for ext in ['.pdf', '.zip', '.jpg', '.jpeg', '.png']):
                if action == "📸 استخراج صور":
                    final_name += ".zip"
                else:
                    final_name += ".pdf"
        else:
            final_name = default_names.get(action, "ملف_جديد.pdf")
        
        await update.message.reply_text("⏳ جاري المعالجة... يرجى الانتظار")
        
        # تنفيذ العملية
        if action == "📎 دمج PDF":
            result_path = PDFEngine.merge(session.files)
            
        elif action == "🖼️ صور لـ PDF":
            result_path = PDFEngine.images_to_pdf(session.files)
            
        elif action == "📸 استخراج صور":
            if len(session.files) != 1:
                await update.message.reply_text("❌ يجب إرسال ملف PDF واحد فقط")
                return SELECT_ACTION
            result_data, filename = PDFEngine.pdf_to_images(session.files[0])
            await update.message.reply_document(
                result_data, 
                filename=filename, 
                caption="✅ تم استخراج الصور بنجاح!", 
                reply_markup=MAIN_MENU
            )
            return SELECT_ACTION
            
        elif action == "🔢 ترقيم الصفحات":
            if len(session.files) != 1:
                await update.message.reply_text("❌ يجب إرسال ملف PDF واحد فقط")
                return SELECT_ACTION
            result_path = PDFEngine.add_page_numbers(session.files[0])
            
        elif action == "📉 ضغط":
            if len(session.files) != 1:
                await update.message.reply_text("❌ يجب إرسال ملف PDF واحد فقط")
                return SELECT_ACTION
            result_path, before_size, after_size = PDFEngine.compress(session.files[0])
            if before_size == after_size:
                extra_info = "\n⚠️ لم يتغير الحجم (الملف مضغوط بالفعل)"
            else:
                reduction = (1 - after_size / before_size) * 100
                extra_info = f"\n📊 {format_size(before_size)} → {format_size(after_size)}\n✅ تم التخفيض بنسبة {reduction:.1f}%"
                
        elif action == "💧 علامة مائية":
            if len(session.files) != 1:
                await update.message.reply_text("❌ يجب إرسال ملف PDF واحد فقط")
                return SELECT_ACTION
            watermark_text = session.val1 or "© جميع الحقوق محفوظة"
            result_path = PDFEngine.add_watermark(session.files[0], watermark_text)
            extra_info = f"\n💧 العلامة: {watermark_text}"
            
        elif action == "🔒 حماية":
            if len(session.files) != 1:
                await update.message.reply_text("❌ يجب إرسال ملف PDF واحد فقط")
                return SELECT_ACTION
            password = session.val1 or "1234"
            result_path = PDFEngine.encrypt(session.files[0], password)
            extra_info = f"\n🔑 كلمة المرور: `{password}`"
            
        elif action == "✂️ تقسيم":
            if len(session.files) != 1:
                await update.message.reply_text("❌ يجب إرسال ملف PDF واحد فقط")
                return SELECT_ACTION
            try:
                reader = PdfReader(session.files[0])
                total_pages = len(reader.pages)
                page_nums = validate_page_range(session.val1 or "1", total_pages)
                result_path = PDFEngine.extract_pages(session.files[0], page_nums)
                extra_info = f"\n📄 تم استخراج {len(page_nums)} صفحة من {total_pages}"
            except Exception as e:
                raise ValueError(f"نطاق الصفحات غير صحيح: {str(e)}")
            
        elif action == "🗑️ حذف صفحات":
            if len(session.files) != 1:
                await update.message.reply_text("❌ يجب إرسال ملف PDF واحد فقط")
                return SELECT_ACTION
            try:
                reader = PdfReader(session.files[0])
                total_pages = len(reader.pages)
                page_nums = validate_page_range(session.val1 or "1", total_pages)
                result_path = PDFEngine.delete_pages(session.files[0], page_nums)
                extra_info = f"\n🗑️ تم حذف {len(page_nums)} صفحة"
            except Exception as e:
                raise ValueError(f"نطاق الصفحات غير صحيح: {str(e)}")
            
        elif action == "🔓 إزالة الحماية":
            if len(session.files) != 1:
                await update.message.reply_text("❌ يجب إرسال ملف PDF واحد فقط")
                return SELECT_ACTION
            result_path = PDFEngine.remove_password(session.files[0])
            extra_info = "\n🔓 تم إزالة كلمة المرور بنجاح"
            
        elif action == "ℹ️ معلومات":
            if len(session.files) != 1:
                await update.message.reply_text("❌ يجب إرسال ملف PDF واحد فقط")
                return SELECT_ACTION
            metadata = PDFEngine.get_metadata(session.files[0])
            info_text = (
                f"📊 **معلومات الملف**\n\n"
                f"📄 عدد الصفحات: {metadata['pages']}\n"
                f"📝 العنوان: {metadata['title']}\n"
                f"✍️ المؤلف: {metadata['author']}\n"
                f"💾 الحجم: {format_size(metadata['size'])}\n"
                f"🔒 مشفر: {'نعم' if metadata['encrypted'] else 'لا'}"
            )
            await update.message.reply_text(info_text, parse_mode="Markdown", reply_markup=MAIN_MENU)
            return SELECT_ACTION
        
        # إرسال النتيجة
        if result_path and os.path.exists(result_path):
            with open(result_path, "rb") as file:
                caption = f"✅ تمت العملية بنجاح{extra_info}"
                await update.message.reply_document(
                    file, 
                    filename=final_name, 
                    caption=caption, 
                    reply_markup=MAIN_MENU
                )
            safe_remove(result_path)
        else:
            await update.message.reply_text("❌ حدث خطأ في معالجة الملف، حاول مرة أخرى", reply_markup=MAIN_MENU)
            
    except Exception as e:
        logger.error(f"خطأ في المعالجة: {e}", exc_info=True)
        await update.message.reply_text(f"❌ خطأ: {str(e)[:200]}", reply_markup=MAIN_MENU)
        
    finally:
        set_user_busy(uid, False)
        for file_path in session.files:
            safe_remove(file_path)
        user_sessions.pop(uid, None)
        
    return SELECT_ACTION

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in user_sessions:
        session = user_sessions[uid]
        for file_path in session.files:
            safe_remove(file_path)
        user_sessions.pop(uid, None)
    await update.message.reply_text("✅ تم إلغاء العملية", reply_markup=MAIN_MENU)
    return SELECT_ACTION

def main():
    if not Config.BOT_TOKEN:
        logger.error("❌ BOT_TOKEN غير موجود في ملف .env")
        return
    
    Config.FORCED_CHANNELS = AdminSystem.load_channels()
    app = ApplicationBuilder().token(Config.BOT_TOKEN).build()
    
    app.add_handler(CallbackQueryHandler(admin_callback_handler, pattern="^admin_"))
    app.add_handler(CommandHandler("admin", admin_command))
    
    conversation_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start), CommandHandler("cancel", cancel)],
        states={
            SELECT_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_action)],
            WAIT_FILE: [MessageHandler(filters.ALL & ~filters.COMMAND, receive_files)],
            WAIT_DATA: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_data)],
            WAIT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)]
        },
        fallbacks=[CommandHandler("start", start), CommandHandler("cancel", cancel)],
        per_user=True
    )
    
    app.add_handler(conversation_handler)
    app.add_error_handler(global_error_handler)
    app.job_queue.run_repeating(cleanup_task, interval=Config.CLEANUP_INTERVAL, first=10)
    
    logger.info("🚀 بوت PDF الاحترافي يعمل الآن!")
    logger.info(f"👑 عدد المشرفين: {len(Config.ADMINS)}")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

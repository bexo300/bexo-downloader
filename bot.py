import os
import tempfile
import zipfile
import fitz
from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.errors import WrongPasswordError
from pypdf.generic import AnnotationBuilder
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler, CallbackQueryHandler
)
from dotenv import load_dotenv
import warnings
from telegram.warnings import PTBUserWarning

# إخفاء تحذيرات التوافق الآمنة
warnings.filterwarnings(action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning)

# إعدادات النظام
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_USERNAME = "bexo50"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 ميجابايت كحد أقصى

# حالات المحادثة
CHECK_SUB, SELECT_ACTION, WAIT_FILE, WAIT_VAL = range(4)
user_data = {}

# لوحات التحكم
main_keyboard = [
    ["📎 دمج ملفات PDF", "🖼️ تحويل صور لـ PDF"],
    ["📸 استخراج صور من PDF", "🔢 ترقيم صفحات PDF"],
    ["✂️ تقسيم PDF", "🗑️ حذف صفحات من PDF"],
    ["📄 استخراج صفحات من PDF", "🔄 تدوير صفحات PDF"],
    ["📉 ضغط حجم PDF", "🖼️ تحويل PDF لصور"],
    ["💧 علامة مائية", "ℹ️ معلومات الملف"],
    ["🔃 إعادة ترتيب", "🔒 حماية بكلمة مرور"],
    ["🔓 إزالة الحماية", "🧹 مسح الملفات"]
]
main_markup = ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)

action_keyboard = [
    ["✅ إنهاء وإجراء العملية", "➕ إضافة ملفات أخرى"]
]
action_markup = ReplyKeyboardMarkup(action_keyboard, resize_keyboard=True)

# ========== دوال المساعدة ==========
async def check_subscription(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """التحقق من اشتراك المستخدم في القناة"""
    try:
        member = await context.bot.get_chat_member(chat_id=f"@{CHANNEL_USERNAME}", user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        return False

def safe_cleanup(paths: list[str]):
    """حذف آمن للملفات والمجلدات المؤقتة"""
    for path in paths:
        try:
            if os.path.isfile(path):
                os.remove(path)
            elif os.path.isdir(path):
                os.rmdir(path)
        except Exception:
            pass

# ========== أوامر البوت ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data[user_id] = {"files": [], "action": None}

    if not await check_subscription(user_id, context):
        keyboard = [
            [InlineKeyboardButton("🔗 اشترك في القناة", url=f"https://t.me/{CHANNEL_USERNAME}")],
            [InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="check_sub")]
        ]
        await update.message.reply_text(
            "⚠️ لاستخدام البوت يجب الاشتراك في القناة أولاً",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return CHECK_SUB

    await update.message.reply_text(
        "👋 مرحباً بك في البوت الشامل لملفات PDF!\nاختر الميزة التي تريدها من القائمة أدناه 👇",
        reply_markup=main_markup
    )
    return SELECT_ACTION

async def verify_sub_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if await check_subscription(user_id, context):
        await query.edit_message_text("✅ تم التحقق من اشتراكك! يمكنك استخدام البوت الآن.")
        await query.message.reply_text("اختر الميزة التي تريدها من القائمة أدناه 👇", reply_markup=main_markup)
        return SELECT_ACTION
    else:
        await query.answer("❌ لم يتم العثور على اشتراكك، يرجى الاشتراك أولاً!", show_alert=True)
        return CHECK_SUB

async def select_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    action = update.message.text
    user_data[user_id]["action"] = action

    prompts = {
        "📎 دمج ملفات PDF": "أرسل ملفات PDF واحدة تلو الأخرى، ثم اختر من الأزرار",
        "🖼️ تحويل صور لـ PDF": "أرسل الصور واحدة تلو الأخرى، ثم اختر من الأزرار",
        "📸 استخراج صور من PDF": "أرسل ملف PDF لاستخراج صوره",
        "🔢 ترقيم صفحات PDF": "أرسل ملف PDF لإضافة أرقام الصفحات",
        "✂️ تقسيم PDF": "أرسل ملف PDF، ثم اكتب نطاق التقسيم مثل: 1-5 أو 3,7,9",
        "🗑️ حذف صفحات من PDF": "أرسل ملف PDF، ثم اكتب أرقام الصفحات المراد حذفها مثل: 2,4,6",
        "📄 استخراج صفحات من PDF": "أرسل ملف PDF، ثم اكتب أرقام الصفحات المراد استخراجها مثل: 1-3,5",
        "🔄 تدوير صفحات PDF": "أرسل ملف PDF، ثم اكتب الزاوية 90 / 180 / 270",
        "📉 ضغط حجم PDF": "أرسل ملف PDF لتقليل حجمه",
        "🖼️ تحويل PDF لصور": "أرسل ملف PDF لتحويل صفحاته لصور",
        "💧 علامة مائية": "أرسل ملف PDF، ثم اكتب النص للعلامة المائية",
        "ℹ️ معلومات الملف": "أرسل ملف PDF لعرض تفاصيله",
        "🔃 إعادة ترتيب": "أرسل ملف PDF، ثم اكتب الترتيب الجديد مثل: 3,1,2,4",
        "🔒 حماية بكلمة مرور": "أرسل ملف PDF، ثم اكتب كلمة المرور",
        "🔓 إزالة الحماية": "أرسل ملف PDF المحمي، ثم اكتب كلمة المرور",
        "🧹 مسح الملفات": "✅ تم مسح جميع الملفات المؤقتة، اختر ميزة جديدة"
    }

    if action == "🧹 مسح الملفات":
        user_data[user_id]["files"] = []
        await update.message.reply_text(prompts[action], reply_markup=main_markup)
        return SELECT_ACTION

    await update.message.reply_text(prompts[action], reply_markup=ReplyKeyboardRemove())
    return WAIT_FILE

async def receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    action = user_data[user_id]["action"]
    text = update.message.text

    if text == "✅ إنهاء وإجراء العملية":
        return await process_action(update, context)
    if text == "➕ إضافة ملفات أخرى":
        await update.message.reply_text("✅ تابع إرسال الملفات، ثم اختر إنهاء عند الانتهاء")
        return WAIT_FILE

    # التعامل مع الملفات المستلمة
    if update.message.document:
        doc = update.message.document
        if doc.file_size > MAX_FILE_SIZE:
            await update.message.reply_text("❌ حجم الملف كبير جدًا! الحد الأقصى 50 ميجابايت.")
            return WAIT_FILE
        if "PDF" in action and not doc.file_name.lower().endswith(".pdf"):
            await update.message.reply_text("❌ أرسل ملف بصيغة PDF فقط!")
            return WAIT_FILE
        
        file = await context.bot.get_file(doc.file_id)
        temp_dir = tempfile.mkdtemp()
        path = os.path.join(temp_dir, doc.file_name)
        await file.download_to_drive(path)
        user_data[user_id]["files"].append(path)

    elif update.message.photo:
        photo = update.message.photo[-1]
        if photo.file_size > MAX_FILE_SIZE:
            await update.message.reply_text("❌ حجم الصورة كبير جدًا!")
            return WAIT_FILE
        
        file = await context.bot.get_file(photo.file_id)
        temp_dir = tempfile.mkdtemp()
        path = os.path.join(temp_dir, f"img_{user_id}{len(user_data[user_id]['files'])}.jpg")
        await file.download_to_drive(path)
        user_data[user_id]["files"].append(path)

    elif text and action not in ["📎 دمج ملفات PDF", "🖼️ تحويل صور لـ PDF"]:
        user_data[user_id]["val1"] = text.strip()
        return await process_action(update, context)

    await update.message.reply_text(
        f"✅ تم استلام الملف | العدد: {len(user_data[user_id]['files'])}\nاختر ما تريد: ",
        reply_markup=action_markup
    )
    return WAIT_FILE

async def process_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = user_data[user_id]
    action = data["action"]
    files = data["files"]
    val1 = data.get("val1", "")
    output_path = ""
    output_filename = ""

    if not files:
        await update.message.reply_text("❌ لم يتم إرسال أي ملف!")
        return SELECT_ACTION

    try:
        # ========== دمج ملفات PDF ==========
        if action == "📎 دمج ملفات PDF":
            if len(files) < 2:
                await update.message.reply_text("❌ يجب إرسال ملفين على الأقل!", reply_markup=main_markup)
                return SELECT_ACTION
            writer = PdfWriter()
            for f in files:
                writer.append(f)
            output_filename = "ملفات_مدمجة.pdf"
            output_path = os.path.join(tempfile.gettempdir(), output_filename)
            writer.write(output_path)
            writer.close()

        # ========== تحويل صور لـ PDF ==========
        elif action == "🖼️ تحويل صور لـ PDF":
            img_list = [Image.open(f).convert("RGB") for f in files]
            output_filename = "صور_محولة_لـ_PDF.pdf"
            output_path = os.path.join(tempfile.gettempdir(), output_filename)
            img_list[0].save(output_path, save_all=True, append_images=img_list[1:])

        # ========== استخراج صور من PDF ==========
        elif action == "📸 استخراج صور من PDF":
            reader = PdfReader(files[0])
            output_filename = "صور_مستخرجة.zip"
            output_path = os.path.join(tempfile.gettempdir(), output_filename)
            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for i, page in enumerate(reader.pages):
                    for j, img in enumerate(page.images):
                        ext = img.name.split(".")[-1]
                        img_path = tempfile.mktemp(suffix=f".{ext}")
                        with open(img_path, "wb") as f:
                            f.write(img.data)
                        zf.write(img_path, arcname=f"صفحة_{i+1}_صورة_{j+1}.{ext}")
                        os.remove(img_path)

        # ========== ترقيم الصفحات ==========
        elif action == "🔢 ترقيم صفحات PDF":
            reader = PdfReader(files[0])
            writer = PdfWriter()
            for num, page in enumerate(reader.pages, start=1):
                watermark = AnnotationBuilder.text(
                    text=str(num), xy=(250, 10), font_size=14
                ).get_page()
                page.merge_page(watermark)
                writer.add_page(page)
            output_filename = "ملف_مرقم_الصفحات.pdf"
            output_path = os.path.join(tempfile.gettempdir(), output_filename)
            writer.write(output_path)
            writer.close()

        # ========== تقسيم / استخراج صفحات ==========
        elif action in ["✂️ تقسيم PDF", "📄 استخراج صفحات من PDF"]:
            reader = PdfReader(files[0])
            writer = PdfWriter()
            for part in val1.replace(" ", "").split(","):
                if "-" in part:
                    s, e = map(int, part.split("-"))
                    for p in range(s-1, min(e, len(reader.pages))):
                        writer.add_page(reader.pages[p])
                else:
                    idx = int(part) - 1
                    if 0 <= idx < len(reader.pages):
                        writer.add_page(reader.pages[idx])
            output_filename = "ملف_مقسم_مستخرج.pdf"
            output_path = os.path.join(tempfile.gettempdir(), output_filename)
            writer.write(output_path)
            writer.close()

        # ========== حذف صفحات ==========
        elif action == "🗑️ حذف صفحات من PDF":
            reader = PdfReader(files[0])
            writer = PdfWriter()
            del_pages = set(map(int, val1.replace(" ", "").split(",")))
            for num, page in enumerate(reader.pages, start=1):
                if num not in del_pages:
                    writer.add_page(page)
            output_filename = "ملف_بعد_حذف_الصفحات.pdf"
            output_path = os.path.join(tempfile.gettempdir(), output_filename)
            writer.write(output_path)
            writer.close()

        # ========== تدوير صفحات ==========
        elif action == "🔄 تدوير صفحات PDF":
            deg = int(val1)
            if deg not in [90, 180, 270]:
                await update.message.reply_text("❌ الزاوية يجب أن تكون 90 أو 180 أو 270 فقط!")
                return WAIT_VAL
            reader = PdfReader(files[0])
            writer = PdfWriter()
            for page in reader.pages:
                page.rotate(deg)
                writer.add_page(page)
            output_filename = "ملف_مدور_الصفحات.pdf"
            output_path = os.path.join(tempfile.gettempdir(), output_filename)
            writer.write(output_path)
            writer.close()

        # ========== ضغط الملف ==========
        elif action == "📉 ضغط حجم PDF":
            reader = PdfReader(files[0])
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            output_filename = "ملف_مضغوط.pdf"
            output_path = os.path.join(tempfile.gettempdir(), output_filename)
            writer.write(output_path)
            writer.close()

        # ========== تحويل PDF لصور ==========
        elif action == "🖼️ تحويل PDF لصور":
            doc = fitz.open(files[0])
            output_filename = "صفحات_محولة_لصور.zip"
            output_path = os.path.join(tempfile.gettempdir(), output_filename)
            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for i, page in enumerate(doc):
                    pix = page.get_pixmap(dpi=200)
                    img_path = tempfile.mktemp(suffix=".jpg")
                    pix.save(img_path)
                    zf.write(img_path, arcname=f"صفحة_{i+1}.jpg")
                    os.remove(img_path)
            doc.close()

        # ========== علامة مائية ==========
        elif action == "💧 علامة مائية":
            reader = PdfReader(files[0])
            writer = PdfWriter()
            watermark = AnnotationBuilder.text(
                text=val1, xy=(200, 300), font_size=25, color=(0, 0, 0, 0.2)
            ).get_page()
            for page in reader.pages:
                page.merge_page(watermark)
                writer.add_page(page)
            output_filename = "ملف_بعلامة_مائية.pdf"
            output_path = os.path.join(tempfile.gettempdir(), output_filename)
            writer.write(output_path)
            writer.close()

        # ========== معلومات الملف ==========
        elif action == "ℹ️ معلومات الملف":
            reader = PdfReader(files[0])
            info = f"""📄 معلومات الملف:
• عدد الصفحات: {len(reader.pages)}
• العنوان: {reader.metadata.title or 'غير محدد'}
• المؤلف: {reader.metadata.author or 'غير محدد'}
• تاريخ الإنشاء: {reader.metadata.creation_date or 'غير محدد'}
• محمي بكلمة مرور: {'نعم' if reader.is_encrypted else 'لا'}"""
            await update.message.reply_text(info, reply_markup=main_markup)
            safe_cleanup(files)
            user_data[user_id] = {"files": [], "action": None}
            return SELECT_ACTION

        # ========== إعادة ترتيب ==========
        elif action == "🔃 إعادة ترتيب":
            order = list(map(int, val1.replace(" ", "").split(",")))
            reader = PdfReader(files[0])
            writer = PdfWriter()
            for num in order:
                idx = num - 1
                if 0 <= idx < len(reader.pages):
                    writer.add_page(reader.pages[idx])
            output_filename = "ملف_معاد_الترتيب.pdf"
            output_path = os.path.join(tempfile.gettempdir(), output_filename)
            writer.write(output_path)
            writer.close()

        # ========== حماية بكلمة مرور ==========
        elif action == "🔒 حماية بكلمة مرور":
            reader = PdfReader(files[0])
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            writer.encrypt(val1, val1, algorithm="AES-256")
            output_filename = "ملف_محمي_بكلمة_مرور.pdf"
            output_path = os.path.join(tempfile.gettempdir(), output_filename)
            writer.write(output_path)
            writer.close()

        # ========== إزالة الحماية ==========
        elif action == "🔓 إزالة الحماية":
            try:
                reader = PdfReader(files[0], password=val1)
                if reader.is_encrypted:
                    await update.message.reply_text("❌ كلمة المرور خاطئة أو الملف تالف!")
                    return WAIT_VAL
                writer = PdfWriter()
                for page in reader.pages:
                    writer.add_page(page)
                output_filename = "ملف_بدون_حماية.pdf"
                output_path = os.path.join(tempfile.gettempdir(), output_filename)
                writer.write(output_path)
                writer.close()
            except WrongPasswordError:
                await update.message.reply_text("❌ كلمة المرور غير صحيحة!")
                return WAIT_VAL

        # إرسال النتيجة
        if output_path and os.path.exists(output_path):
            caption = f"✅ تمت العملية بنجاح!\nاسم الملف: {output_filename}"
            if output_path.endswith(".zip"):
                caption = f"✅ تمت العملية بنجاح!\nاسم الملف المضغوط: {output_filename}"
            await update.message.reply_document(
                document=open(output_path, "rb"),
                caption=caption,
                filename=output_filename,
                reply_markup=main_markup
            )

    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ: {str(e)[:150]}", reply_markup=main_markup)
    finally:
        # تنظيف إجباري لكل الملفات المؤقتة
        all_paths = files + ([output_path] if output_path else [])
        safe_cleanup(all_paths)
        user_data[user_id] = {"files": [], "action": None}

    return SELECT_ACTION

# ========== تشغيل البوت ==========
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHECK_SUB: [CallbackQueryHandler(verify_sub_callback)],
            SELECT_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_action)],
            WAIT_FILE: [
                MessageHandler(filters.ALL & ~filters.COMMAND, receive_file)
            ]
        },
        fallbacks=[CommandHandler("start", start)],
        per_chat=True,
        per_user=True,
        per_message=False
    )
    app.add_handler(conv_handler)
    print("✅ البوت يعمل بنظام الاشتراك الإجباري... جاهز للاستخدام")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

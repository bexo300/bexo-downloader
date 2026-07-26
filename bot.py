import os
import tempfile
import zipfile
from pypdf import PdfMerger, PdfReader, PdfWriter, PageObject
from pypdf.generic import AnnotationBuilder
from PIL import Image
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

user_data = {}
SELECT_ACTION, WAIT_FILE, WAIT_VAL1, WAIT_VAL2 = range(4)

# لوحة التحكم الرئيسية
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
reply_markup = ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data[user_id] = {"files": [], "action": None}
    await update.message.reply_text(
        "👋 مرحباً بك في البوت الشامل لملفات PDF!\n"
        "اختر الميزة التي تريدها من القائمة أدناه 👇",
        reply_markup=reply_markup
    )
    return SELECT_ACTION

async def select_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    action = update.message.text
    user_data[user_id]["action"] = action
    
    prompts = {
        "📎 دمج ملفات PDF": "أرسل ملفات PDF واحدة تلو الأخرى، ثم أرسل ✅ تم الانتهاء",
        "🖼️ تحويل صور لـ PDF": "أرسل الصور واحدة تلو الأخرى، ثم أرسل ✅ تم الانتهاء",
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
        "🧹 مسح الملفات": "تم مسح جميع الملفات المؤقتة، اختر ميزة جديدة"
    }
    
    if action == "🧹 مسح الملفات":
        user_data[user_id]["files"] = []
        await update.message.reply_text(prompts[action], reply_markup=reply_markup)
        return SELECT_ACTION
    
    await update.message.reply_text(prompts[action], reply_markup=ReplyKeyboardRemove())
    return WAIT_FILE

async def receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    action = user_data[user_id]["action"]
    
    if update.message.document:
        doc = update.message.document
        if "PDF" in action and doc.mime_type != "application/pdf":
            await update.message.reply_text("❌ أرسل ملف PDF فقط!")
            return WAIT_FILE
        file = await context.bot.get_file(doc.file_id)
        path = os.path.join(tempfile.mkdtemp(), doc.file_name)
        await file.download_to_drive(path)
        user_data[user_id]["files"].append(path)
        
    elif update.message.photo:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        path = os.path.join(tempfile.mkdtemp(), f"img_{user_id}{len(user_data[user_id]['files'])}.jpg")
        await file.download_to_drive(path)
        user_data[user_id]["files"].append(path)
    
    elif update.message.text == "✅ تم الانتهاء":
        return await process_action(update, context)
    
    elif update.message.text:
        user_data[user_id]["val1"] = update.message.text
        if action in ["✂️ تقسيم PDF", "🗑️ حذف صفحات من PDF", "📄 استخراج صفحات من PDF", "🔄 تدوير صفحات PDF", "💧 علامة مائية", "🔃 إعادة ترتيب", "🔒 حماية بكلمة مرور", "🔓 إزالة الحماية"]:
            return await process_action(update, context)
    
    await update.message.reply_text("✅ تم استلام الملف، أرسل المزيد أو أرسل ✅ تم الانتهاء")
    return WAIT_FILE

async def process_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = user_data[user_id]
    action = data["action"]
    files = data["files"]
    val1 = data.get("val1", "")
    
    try:
        output_path = ""
        if action == "📎 دمج ملفات PDF":
            merger = PdfMerger()
            for f in files: merger.append(f)
            output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
            merger.write(output_path)
            merger.close()

        elif action == "🖼️ تحويل صور لـ PDF":
            img_list = [Image.open(f).convert("RGB") for f in files]
            output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
            img_list[0].save(output_path, save_all=True, append_images=img_list[1:])

        elif action == "📸 استخراج صور من PDF":
            reader = PdfReader(files[0])
            zip_path = tempfile.NamedTemporaryFile(delete=False, suffix=".zip").name
            with zipfile.ZipFile(zip_path, "w") as zf:
                for i, page in enumerate(reader.pages):
                    for j, img in enumerate(page.images):
                        img_path = f"page_{i+1}_img_{j+1}.{img.name.split('.')[-1]}"
                        open(img_path, "wb").write(img.data)
                        zf.write(img_path)
                        os.remove(img_path)
            output_path = zip_path

        elif action == "🔢 ترقيم صفحات PDF":
            reader = PdfReader(files[0])
            writer = PdfWriter()
            for i, page in enumerate(reader.pages):
                page.merge_page(AnnotationBuilder.text(str(i+1), (50,20), font_size=12).get_page())
                writer.add_page(page)
            output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
            writer.write(output_path)

        elif action == "✂️ تقسيم PDF":
            reader = PdfReader(files[0])
            writer = PdfWriter()
            for rng in val1.replace(" ", "").split(","):
                if "-" in rng:
                    s,e = map(int, rng.split("-"))
                    for p in range(s-1,e): writer.add_page(reader.pages[p])
                else: writer.add_page(reader.pages[int(rng)-1])
            output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
            writer.write(output_path)

        elif action == "🗑️ حذف صفحات من PDF":
            reader = PdfReader(files[0])
            writer = PdfWriter()
            del_pages = set(map(int, val1.replace(" ", "").split(",")))
            for i in range(len(reader.pages)):
                if i+1 not in del_pages: writer.add_page(reader.pages[i])
            output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
            writer.write(output_path)

        elif action == "📄 استخراج صفحات من PDF":
            reader = PdfReader(files[0])
            writer = PdfWriter()
            for rng in val1.replace(" ", "").split(","):
                if "-" in rng:
                    s,e = map(int, rng.split("-"))
                    for p in range(s-1,e): writer.add_page(reader.pages[p])
                else: writer.add_page(reader.pages[int(rng)-1])
            output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
            writer.write(output_path)

        elif action == "🔄 تدوير صفحات PDF":
            deg = int(val1)
            reader = PdfReader(files[0])
            writer = PdfWriter()
            for page in reader.pages:
                page.rotate(deg)
                writer.add_page(page)
            output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
            writer.write(output_path)

        elif action == "📉 ضغط حجم PDF":
            reader = PdfReader(files[0])
            writer = PdfWriter()
            for page in reader.pages: writer.add_page(page)
            output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
            writer.write(output_path)

        elif action == "🖼️ تحويل PDF لصور":
            reader = PdfReader(files[0])
            zip_path = tempfile.NamedTemporaryFile(delete=False, suffix=".zip").name
            with zipfile.ZipFile(zip_path, "w") as zf:
                for i, page in enumerate(reader.pages):
                    pix = page.to_image()
                    img_path = f"page_{i+1}.jpg"
                    pix.save(img_path)
                    zf.write(img_path)
                    os.remove(img_path)
            output_path = zip_path

        elif action == "💧 علامة مائية":
            reader = PdfReader(files[0])
            water = AnnotationBuilder.text(val1, (250,400), font_size=30, color=(0,0,0,0.3)).get_page()
            writer = PdfWriter()
            for page in reader.pages:
                page.merge_page(water)
                writer.add_page(page)
            output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
            writer.write(output_path)

        elif action == "ℹ️ معلومات الملف":
            reader = PdfReader(files[0])
            info = f"📄 عدد الصفحات: {len(reader.pages)}\n📌 العنوان: {reader.metadata.title or 'غير محدد'}\n✍️ المؤلف: {reader.metadata.author or 'غير محدد'}"
            await update.message.reply_text(info, reply_markup=reply_markup)
            user_data[user_id] = {"files": [], "action": None}
            return SELECT_ACTION

        elif action == "🔃 إعادة ترتيب":
            order = list(map(int, val1.replace(" ", "").split(",")))
            reader = PdfReader(files[0])
            writer = PdfWriter()
            for num in order: writer.add_page(reader.pages[num-1])
            output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
            writer.write(output_path)

        elif action == "🔒 حماية بكلمة مرور":
            reader = PdfReader(files[0])
            writer = PdfWriter()
            for page in reader.pages: writer.add_page(page)
            writer.encrypt(val1)
            output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
            writer.write(output_path)

        elif action == "🔓 إزالة الحماية":
            reader = PdfReader(files[0], password=val1)
            writer = PdfWriter()
            for page in reader.pages: writer.add_page(page)
            output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
            writer.write(output_path)

        # إرسال النتيجة
        with open(output_path, "rb") as f:
            if output_path.endswith(".zip"):
                await update.message.reply_document(f, caption="✅ تمت العملية، الملفات مضغوطة بالملف المرفق", reply_markup=reply_markup)
            else:
                await update.message.reply_document(f, caption="✅ تمت العملية بنجاح!", reply_markup=reply_markup)

    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {str(e)}", reply_markup=reply_markup)
    finally:
        # تنظيف الملفات
        for f in files: 
            os.remove(f)
            os.rmdir(os.path.dirname(f))
        if output_path and os.path.exists(output_path): os.remove(output_path)
        user_data[user_id] = {"files": [], "action": None}
    return SELECT_ACTION

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SELECT_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_action)],
            WAIT_FILE: [MessageHandler(filters.ALL & ~filters.COMMAND, receive_file)]
        },
        fallbacks=[CommandHandler('start', start)]
    )
    app.add_handler(conv_handler)
    print("✅ البوت الشامل يعمل الآن...")
    app.run_polling()

if __name__ == "__main__":
    main()

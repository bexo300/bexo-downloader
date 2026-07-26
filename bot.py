import os
import re
import tempfile
import shutil
import zipfile
import io
import asyncio
import logging
import warnings
from logging.handlers import RotatingFileHandler
from dataclasses import dataclass, field
from typing import List, Set, Optional
from dotenv import load_dotenv
import fitz
from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.errors import WrongPasswordError
from pypdf.annotations import FreeText
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler, CallbackQueryHandler
)
from telegram.warnings import PTBUserWarning

# ==============================================
# 🔧 الإعدادات العامة
# ==============================================
warnings.filterwarnings(action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning)
load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    CHANNEL_USERNAME = "bexo50"
    MAX_FILE_SIZE = 50 * 1024 * 1024
    MAX_FILES_PER_MERGE = 20
    MAX_PAGES_PER_SPLIT = 100
    TEMP_DIR = os.path.join(os.path.dirname(__file__), "temp")
    COMPRESSION_QUALITY = "medium"
    LOG_LEVEL = "INFO"
    LOG_FILE = "bot.log"
    LOG_MAX_SIZE = 10 * 1024 * 1024
    LOG_BACKUP_COUNT = 5
    CACHE_TTL = 3600

    @classmethod
    def ensure_directories(cls):
        os.makedirs(cls.TEMP_DIR, exist_ok=True)

# ==============================================
# 📝 نظام التسجيل
# ==============================================
def setup_logging():
    logger = logging.getLogger('pdf_bot')
    logger.setLevel(getattr(logging, Config.LOG_LEVEL))
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler = RotatingFileHandler(
        Config.LOG_FILE, maxBytes=Config.LOG_MAX_SIZE,
        backupCount=Config.LOG_BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger

logger = setup_logging()

# ==============================================
# 🛡️ أدوات الأمان والتحقق
# ==============================================
def validate_page_range(range_str: str, total_pages: int) -> List[int]:
    if not range_str or not range_str.strip():
        raise ValueError("يجب إدخال نطاق الصفحات")
    range_str = range_str.replace(" ", "")
    if not re.match(r'^(\d+(-\d+)?)(,\d+(-\d+)?)*$', range_str):
        raise ValueError("تنسيق غير صحيح. استخدم مثلاً: 1-5 أو 1,3,5")
    pages: Set[int] = set()
    for part in range_str.split(','):
        if '-' in part:
            start, end = map(int, part.split('-'))
            if start < 1 or end > total_pages or start > end:
                raise ValueError(f"نطاق {start}-{end} غير صحيح")
            pages.update(range(start, end + 1))
        else:
            page = int(part)
            if not (1 <= page <= total_pages):
                raise ValueError(f"رقم الصفحة {page} غير موجود")
            pages.add(page)
    return sorted(pages)

def validate_password(password: str) -> bool:
    return bool(password and len(password.strip()) >= 4)

# ==============================================
# 👤 إدارة جلسات المستخدمين - أضفنا حقل اسم الملف
# ==============================================
@dataclass
class UserSession:
    user_id: int
    files: List[str] = field(default_factory=list)
    temp_dirs: List[str] = field(default_factory=list)
    action: Optional[str] = None
    val1: Optional[str] = None
    custom_name: Optional[str] = None  # ✅ اسم الملف المخصص
    expecting_name: bool = False        # ✅ علامة انتظار الاسم

    def add_file(self, file_path: str, temp_dir: str = None):
        self.files.append(file_path)
        if temp_dir: self.temp_dirs.append(temp_dir)

    def cleanup(self):
        for path in self.files:
            try: os.path.isfile(path) and os.remove(path)
            except Exception as e: logger.warning(f"حذف ملف: {e}")
        for d in self.temp_dirs:
            try: os.path.isdir(d) and shutil.rmtree(d, ignore_errors=True)
            except Exception as e: logger.warning(f"حذف مجلد: {e}")
        self.files.clear()
        self.temp_dirs.clear()
        self.val1 = None
        self.custom_name = None
        self.expecting_name = False

    def reset(self):
        self.cleanup()
        self.action = None

# ==============================================
# 📂 إدارة الملفات
# ==============================================
class FileManager:
    @staticmethod
    async def download_file(file, user_id: int, suffix: str = ""):
        temp_dir = tempfile.mkdtemp(dir=Config.TEMP_DIR)
        path = os.path.join(temp_dir, f"file_{user_id}_{suffix}")
        await file.download_to_drive(path)
        return path, temp_dir

    @staticmethod
    def get_temp_file(suffix: str = ""):
        return tempfile.mktemp(suffix=suffix, dir=Config.TEMP_DIR)

# ==============================================
# ⚙️ معالج ملفات PDF
# ==============================================
class PDFProcessor:
    @staticmethod
    def merge_pdfs(paths: List[str]) -> str:
        writer = PdfWriter()
        for p in paths: writer.append(p)
        out = FileManager.get_temp_file(".pdf")
        with open(out, "wb") as f: writer.write(f)
        writer.close()
        return out

    @staticmethod
    def images_to_pdf(paths: List[str]) -> str:
        imgs = [Image.open(p).convert("RGB") for p in paths]
        out = FileManager.get_temp_file(".pdf")
        imgs[0].save(out, save_all=True, append_images=imgs[1:])
        return out

    @staticmethod
    def extract_images(path: str) -> bytes:
        reader = PdfReader(path)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, pg in enumerate(reader.pages):
                for j, img in enumerate(pg.images):
                    ext = img.name.split(".")[-1] if "." in img.name else "jpg"
                    zf.writestr(f"صفحة_{i+1}_صورة_{j+1}.{ext}", img.data)
        buf.seek(0)
        return buf.getvalue()

    @staticmethod
    def add_page_numbers(path: str) -> str:
        reader = PdfReader(path)
        writer = PdfWriter()
        for num, page in enumerate(reader.pages, start=1):
            annotation = FreeText(
                text=str(num), rect=(240, 5, 270, 25),
                font_size="14pt", font_color="000000",
                border_color=None, background_color=None
            )
            annotation.flags = 4
            writer.add_page(page)
            writer.add_annotation(page_number=len(writer.pages)-1, annotation=annotation)
        out = FileManager.get_temp_file(".pdf")
        with open(out, "wb") as f: writer.write(f)
        writer.close()
        return out

    @staticmethod
    def split_pdf(path: str, pages: List[int]) -> str:
        reader = PdfReader(path)
        writer = PdfWriter()
        for p in pages: writer.add_page(reader.pages[p-1])
        out = FileManager.get_temp_file(".pdf")
        with open(out, "wb") as f: writer.write(f)
        writer.close()
        return out

    @staticmethod
    def delete_pages(path: str, to_del: List[int]) -> str:
        reader = PdfReader(path)
        writer = PdfWriter()
        del_set = set(to_del)
        for n, pg in enumerate(reader.pages, 1):
            if n not in del_set: writer.add_page(pg)
        out = FileManager.get_temp_file(".pdf")
        with open(out, "wb") as f: writer.write(f)
        writer.close()
        return out

    @staticmethod
    def rotate_pages(path: str, deg: int) -> str:
        reader = PdfReader(path)
        writer = PdfWriter()
        for pg in reader.pages:
            pg.rotate(deg)
            writer.add_page(pg)
        out = FileManager.get_temp_file(".pdf")
        with open(out, "wb") as f: writer.write(f)
        writer.close()
        return out

    @staticmethod
    def compress_pdf(path: str) -> str:
        reader = PdfReader(path)
        writer = PdfWriter()
        for pg in reader.pages:
            pg.compress_content_streams(level=9)
            writer.add_page(pg)
        out = FileManager.get_temp_file(".pdf")
        with open(out, "wb") as f: writer.write(f)
        writer.close()
        return out

    @staticmethod
    def pdf_to_images(path: str, dpi=200) -> bytes:
        doc = fitz.open(path)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, pg in enumerate(doc):
                pix = pg.get_pixmap(dpi=dpi)
                zf.writestr(f"صفحة_{i+1}.jpg", pix.tobytes("jpeg"))
        doc.close()
        buf.seek(0)
        return buf.getvalue()

    @staticmethod
    def add_watermark(path: str, text: str) -> str:
        reader = PdfReader(path)
        writer = PdfWriter()
        for page in reader.pages:
            annotation = FreeText(
                text=text, rect=(150, 380, 350, 420),
                font_size="30pt", font_color="000000",
                border_color=None, background_color=None
            )
            annotation.flags = 4
            writer.add_page(page)
            writer.add_annotation(page_number=len(writer.pages)-1, annotation=annotation)
        out = FileManager.get_temp_file(".pdf")
        with open(out, "wb") as f: writer.write(f)
        writer.close()
        return out

    @staticmethod
    def get_info(path: str) -> dict:
        r = PdfReader(path)
        return {
            "pages": len(r.pages), "title": r.metadata.title or "غير محدد",
            "author": r.metadata.author or "غير محدد", "encrypted": r.is_encrypted,
            "size": os.path.getsize(path)
        }

    @staticmethod
    def reorder_pages(path: str, order: List[int]) -> str:
        reader = PdfReader(path)
        writer = PdfWriter()
        for n in order: writer.add_page(reader.pages[n-1])
        out = FileManager.get_temp_file(".pdf")
        with open(out, "wb") as f: writer.write(f)
        writer.close()
        return out

    @staticmethod
    def encrypt(path: str, pw: str) -> str:
        reader = PdfReader(path)
        writer = PdfWriter()
        for pg in reader.pages: writer.add_page(pg)
        writer.encrypt(pw, pw, algorithm="AES-256")
        out = FileManager.get_temp_file(".pdf")
        with open(out, "wb") as f: writer.write(f)
        writer.close()
        return out

    @staticmethod
    def decrypt(path: str, pw: str) -> str:
        reader = PdfReader(path, password=pw)
        if reader.is_encrypted: raise WrongPasswordError("كلمة المرور خاطئة")
        writer = PdfWriter()
        for pg in reader.pages: writer.add_page(pg)
        out = FileManager.get_temp_file(".pdf")
        with open(out, "wb") as f: writer.write(f)
        writer.close()
        return out

# ==============================================
# 🎛️ معالج أوامر البوت - معدل لدعم تسمية الملف
# ==============================================
MAIN_MENU = [
    ["📎 دمج ملفات PDF", "🖼️ تحويل صور لـ PDF"],
    ["📸 استخراج صور من PDF", "🔢 ترقيم صفحات PDF"],
    ["✂️ تقسيم PDF", "🗑️ حذف صفحات من PDF"],
    ["📄 استخراج صفحات من PDF", "🔄 تدوير صفحات PDF"],
    ["📉 ضغط حجم PDF", "🖼️ تحويل PDF لصور"],
    ["💧 علامة مائية", "ℹ️ معلومات الملف"],
    ["🔃 إعادة ترتيب", "🔒 حماية بكلمة مرور"],
    ["🔓 إزالة الحماية", "🧹 مسح الملفات"]
]
MAIN_KB = ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True)
ACTION_KB = ReplyKeyboardMarkup([["✅ إنهاء وإجراء العملية", "➕ إضافة ملفات أخرى"]], resize_keyboard=True)

# أسماء الملفات الافتراضية لكل ميزة
DEFAULT_NAMES = {
    "📎 دمج ملفات PDF": "ملفات_مدمجة.pdf",
    "🖼️ تحويل صور لـ PDF": "صور_محولة.pdf",
    "📸 استخراج صور من PDF": "صور_مستخرجة.zip",
    "🔢 ترقيم صفحات PDF": "ملف_مرقم.pdf",
    "✂️ تقسيم PDF": "ملف_مقسم.pdf",
    "🗑️ حذف صفحات من PDF": "ملف_بعد_الحذف.pdf",
    "📄 استخراج صفحات من PDF": "ملف_مستخرج.pdf",
    "🔄 تدوير صفحات PDF": "ملف_مدور.pdf",
    "📉 ضغط حجم PDF": "ملف_مضغوط.pdf",
    "🖼️ تحويل PDF لصور": "صفحات_صور.zip",
    "💧 علامة مائية": "ملف_بعلامة.pdf",
    "🔃 إعادة ترتيب": "ملف_مرتب.pdf",
    "🔒 حماية بكلمة مرور": "ملف_محمي.pdf",
    "🔓 إزالة الحماية": "ملف_بدون_حماية.pdf"
}

PROMPTS = {
    "📎 دمج ملفات PDF": "أرسل ملفات PDF واحدة تلو الأخرى، ثم اختر إنهاء",
    "🖼️ تحويل صور لـ PDF": "أرسل الصور واحدة تلو الأخرى، ثم اختر إنهاء",
    "📸 استخراج صور من PDF": "أرسل ملف PDF لاستخراج صوره",
    "🔢 ترقيم صفحات PDF": "أرسل ملف PDF لإضافة أرقام الصفحات",
    "✂️ تقسيم PDF": "أرسل ملف PDF ثم نطاق التقسيم (مثال: 1-5)",
    "🗑️ حذف صفحات من PDF": "أرسل ملف PDF ثم أرقام الصفحات للحذف",
    "📄 استخراج صفحات من PDF": "أرسل ملف PDF ثم نطاق الصفحات المطلوبة",
    "🔄 تدوير صفحات PDF": "أرسل ملف PDF ثم الزاوية 90/180/270",
    "📉 ضغط حجم PDF": "أرسل ملف PDF لتقليل حجمه",
    "🖼️ تحويل PDF لصور": "أرسل ملف PDF لتحويله لصور",
    "💧 علامة مائية": "أرسل ملف PDF ثم نص العلامة المائية",
    "ℹ️ معلومات الملف": "أرسل ملف PDF لعرض تفاصيله",
    "🔃 إعادة ترتيب": "أرسل ملف PDF ثم الترتيب الجديد",
    "🔒 حماية بكلمة مرور": "أرسل ملف PDF ثم كلمة المرور",
    "🔓 إزالة الحماية": "أرسل الملف المحمي ثم كلمة المرور",
    "🧹 مسح الملفات": "✅ تم مسح جميع الملفات المؤقتة"
}

user_sessions = {}
CHECK_SUB, SELECT_ACTION, WAIT_FILE, WAIT_NAME = range(4)  # ✅ أضفنا حالة انتظار الاسم

async def check_sub(user_id: int, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        m = await ctx.bot.get_chat_member(f"@{Config.CHANNEL_USERNAME}", user_id)
        return m.status in ["member", "administrator", "creator"]
    except: return False

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in user_sessions: user_sessions[uid].reset()
    if not await check_sub(uid, ctx):
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 اشترك في القناة", url=f"https://t.me/{Config.CHANNEL_USERNAME}")],
            [InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="check_sub")]
        ])
        await update.message.reply_text("⚠️ يجب الاشتراك في القناة أولاً", reply_markup=kb)
        return CHECK_SUB
    user_sessions[uid] = UserSession(user_id=uid)
    await update.message.reply_text("👋 مرحباً! اختر الميزة المطلوبة 👇", reply_markup=MAIN_KB)
    return SELECT_ACTION

async def verify_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if await check_sub(q.from_user.id, ctx):
        await q.edit_message_text("✅ تم التحقق! يمكنك الاستخدام الآن")
        await q.message.reply_text("اختر الميزة 👇", reply_markup=MAIN_KB)
        return SELECT_ACTION
    await q.answer("❌ لم يتم العثور على اشتراكك!", show_alert=True)
    return CHECK_SUB

async def choose_action(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    act = update.message.text
    if uid not in user_sessions: user_sessions[uid] = UserSession(uid)
    s = user_sessions[uid]
    s.action = act
    if act == "🧹 مسح الملفات":
        s.cleanup()
        await update.message.reply_text(PROMPTS[act], reply_markup=MAIN_KB)
        return SELECT_ACTION
    await update.message.reply_text(PROMPTS.get(act, "اختر من القائمة"), reply_markup=ReplyKeyboardRemove())
    return WAIT_FILE

async def receive(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    s = user_sessions.get(uid)
    if not s or not s.action:
        await update.message.reply_text("اختر ميزة أولاً", reply_markup=MAIN_KB)
        return SELECT_ACTION

    # ✅ إذا كنا ننتظر اسم الملف
    if s.expecting_name:
        name = update.message.text.strip()
        if name:
            s.custom_name = name
        else:
            s.custom_name = None
        return await process(update, ctx, s)

    txt = update.message.text
    if txt == "✅ إنهاء وإجراء العملية":
        # ✅ بعد الضغط على إنهاء اسأل عن الاسم
        await update.message.reply_text("📝 أرسل اسم الملف الجديد (أو اضغط إرسال مباشرة لاستخدام الاسم الافتراضي):")
        s.expecting_name = True
        return WAIT_NAME

    if txt == "➕ إضافة ملفات أخرى":
        await update.message.reply_text("أرسل المزيد ثم اختر إنهاء")
        return WAIT_FILE

    if update.message.document:
        doc = update.message.document
        if doc.file_size > Config.MAX_FILE_SIZE:
            await update.message.reply_text("❌ الحد الأقصى 50 ميجابايت")
            return WAIT_FILE
        if "PDF" in s.action and not doc.file_name.lower().endswith(".pdf"):
            await update.message.reply_text("❌ أرسل ملف PDF فقط")
            return WAIT_FILE
        f = await ctx.bot.get_file(doc.file_id)
        path, d = await FileManager.download_file(f, uid, f"_{len(s.files)}")
        s.add_file(path, d)
        await update.message.reply_text(f"✅ تم استلام | العدد: {len(s.files)}", reply_markup=ACTION_KB)
        return WAIT_FILE

    if update.message.photo:
        ph = update.message.photo[-1]
        if ph.file_size > Config.MAX_FILE_SIZE:
            await update.message.reply_text("❌ حجم الصورة كبير جداً")
            return WAIT_FILE
        f = await ctx.bot.get_file(ph.file_id)
        path, d = await FileManager.download_file(f, uid, f"_img_{len(s.files)}.jpg")
        s.add_file(path, d)
        await update.message.reply_text(f"✅ تم استلام الصورة | العدد: {len(s.files)}", reply_markup=ACTION_KB)
        return WAIT_FILE

    if txt:
        s.val1 = txt.strip()
        await update.message.reply_text("📝 أرسل اسم الملف الجديد (أو اضغط إرسال مباشرة لاستخدام الاسم الافتراضي):")
        s.expecting_name = True
        return WAIT_NAME

    await update.message.reply_text("أرسل ملف أو نص صحيح")
    return WAIT_FILE

async def process(update: Update, ctx: ContextTypes.DEFAULT_TYPE, s: UserSession):
    if not s.files:
        await update.message.reply_text("❌ لم يتم إرسال ملفات", reply_markup=MAIN_KB)
        return SELECT_ACTION
    try:
        act = s.action
        res = None
        # ✅ تحديد اسم الملف النهائي
        def_name = DEFAULT_NAMES.get(act, "ملف_جديد.pdf")
        if s.custom_name:
            # إضافة الامتداد تلقائياً إذا لم يضفه المستخدم
            if def_name.endswith(".pdf") and not s.custom_name.lower().endswith(".pdf"):
                final_name = s.custom_name + ".pdf"
            elif def_name.endswith(".zip") and not s.custom_name.lower().endswith(".zip"):
                final_name = s.custom_name + ".zip"
            else:
                final_name = s.custom_name
        else:
            final_name = def_name

        if act == "📎 دمج ملفات PDF":
            if len(s.files) < 2: raise ValueError("مطلوب ملفان على الأقل")
            res = {"p": await asyncio.to_thread(PDFProcessor.merge_pdfs, s.files), "n": final_name, "c": "✅ تم الدمج"}
        elif act == "🖼️ تحويل صور لـ PDF":
            res = {"p": await asyncio.to_thread(PDFProcessor.images_to_pdf, s.files), "n": final_name, "c": "✅ تم التحويل"}
        elif act == "📸 استخراج صور من PDF":
            b = await asyncio.to_thread(PDFProcessor.extract_images, s.files[0])
            p = FileManager.get_temp_file(".zip")
            with open(p, "wb") as f: f.write(b)
            res = {"p": p, "n": final_name, "c": "✅ تم الاستخراج"}
        elif act == "🔢 ترقيم صفحات PDF":
            res = {"p": await asyncio.to_thread(PDFProcessor.add_page_numbers, s.files[0]), "n": final_name, "c": "✅ تم الترقيم"}
        elif act in ["✂️ تقسيم PDF", "📄 استخراج صفحات من PDF"]:
            r = PdfReader(s.files[0])
            pg = validate_page_range(s.val1, len(r.pages))
            res = {"p": await asyncio.to_thread(PDFProcessor.split_pdf, s.files[0], pg), "n": final_name, "c": f"✅ {len(pg)} صفحة"}
        elif act == "🗑️ حذف صفحات من PDF":
            r = PdfReader(s.files[0])
            pg = validate_page_range(s.val1, len(r.pages))
            res = {"p": await asyncio.to_thread(PDFProcessor.delete_pages, s.files[0], pg), "n": final_name, "c": f"✅ تم حذف {len(pg)} صفحة"}
        elif act == "🔄 تدوير صفحات PDF":
            res = {"p": await asyncio.to_thread(PDFProcessor.rotate_pages, s.files[0], int(s.val1)), "n": final_name, "c": f"✅ دوران {s.val1}°"}
        elif act == "📉 ضغط حجم PDF":
            res = {"p": await asyncio.to_thread(PDFProcessor.compress_pdf, s.files[0]), "n": final_name, "c": "✅ تم الضغط"}
        elif act == "🖼️ تحويل PDF لصور":
            b = await asyncio.to_thread(PDFProcessor.pdf_to_images, s.files[0])
            p = FileManager.get_temp_file(".zip")
            with open(p, "wb") as f: f.write(b)
            res = {"p": p, "n": final_name, "c": "✅ تم التحويل"}
        elif act == "💧 علامة مائية":
            res = {"p": await asyncio.to_thread(PDFProcessor.add_watermark, s.files[0], s.val1), "n": final_name, "c": f"✅ تم إضافة: {s.val1}"}
        elif act == "ℹ️ معلومات الملف":
            i = await asyncio.to_thread(PDFProcessor.get_info, s.files[0])
            await update.message.reply_text(
                f"📄 معلومات الملف:\n• الصفحات: {i['pages']}\n• العنوان: {i['title']}\n• المؤلف: {i['author']}\n• محمي: {'نعم' if i['encrypted'] else 'لا'}\n• الحجم: {i['size']//1024} كيلوبايت",
                reply_markup=MAIN_KB
            )
            s.cleanup()
            s.action = None
            return SELECT_ACTION
        elif act == "🔃 إعادة ترتيب":
            ordr = list(map(int, s.val1.replace(" ","").split(",")))
            res = {"p": await asyncio.to_thread(PDFProcessor.reorder_pages, s.files[0], ordr), "n": final_name, "c": "✅ تم إعادة الترتيب"}
        elif act == "🔒 حماية بكلمة مرور":
            if not validate_password(s.val1): raise ValueError("كلمة المرور 4 أحرف على الأقل")
            res = {"p": await asyncio.to_thread(PDFProcessor.encrypt, s.files[0], s.val1), "n": final_name, "c": "✅ تم الحماية"}
        elif act == "🔓 إزالة الحماية":
            try:
                res = {"p": await asyncio.to_thread(PDFProcessor.decrypt, s.files[0], s.val1), "n": final_name, "c": "✅ تم إزالة الحماية"}
            except WrongPasswordError:
                raise ValueError("❌ كلمة المرور خاطئة")

        if res:
            with open(res["p"], "rb") as f:
                await update.message.reply_document(f, filename=res["n"], caption=res["c"], reply_markup=MAIN_KB)
            os.path.exists(res["p"]) and os.remove(res["p"])
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {str(e)[:150]}", reply_markup=MAIN_KB)
        logger.error(f"خطأ: {e}")
    finally:
        s.cleanup()
        s.action = None
    return SELECT_ACTION

# ==============================================
# 🚀 تشغيل البوت
# ==============================================
def main():
    if not Config.BOT_TOKEN:
        logger.error("لم يتم العثور على BOT_TOKEN")
        return
    Config.ensure_directories()
    app = ApplicationBuilder().token(Config.BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHECK_SUB: [CallbackQueryHandler(verify_cb, pattern="check_sub")],
            SELECT_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_action)],
            WAIT_FILE: [MessageHandler(filters.ALL & ~filters.COMMAND, receive)],
            WAIT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive)]
        },
        fallbacks=[CommandHandler("start", start)],
        per_chat=True, per_user=True, per_message=False
    )
    app.add_handler(conv)
    logger.info("🚀 البوت يعمل مع خاصية تسمية الملفات لجميع الميزات!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

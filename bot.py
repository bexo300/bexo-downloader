# ==================== config.py ====================
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    CHANNEL_USERNAME = "bexo50"
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
    MAX_FILES_PER_MERGE = 20
    MAX_PAGES_PER_SPLIT = 100
    TEMP_DIR = os.path.join(os.path.dirname(__file__), "temp")
    
    # إعدادات الضغط
    COMPRESSION_QUALITY = "medium"  # low, medium, high
    
    # إعدادات التسجيل
    LOG_LEVEL = "INFO"
    LOG_FILE = "bot.log"
    LOG_MAX_SIZE = 10 * 1024 * 1024  # 10 MB
    LOG_BACKUP_COUNT = 5
    
    # إعدادات التخزين المؤقت
    CACHE_TTL = 3600  # ثانية
    
    @classmethod
    def ensure_directories(cls):
        """إنشاء المجلدات المطلوبة"""
        os.makedirs(cls.TEMP_DIR, exist_ok=True)

# ==================== utils/logger.py ====================
import logging
from logging.handlers import RotatingFileHandler
from config import Config

def setup_logging():
    """إعداد نظام التسجيل"""
    logger = logging.getLogger('pdf_bot')
    logger.setLevel(getattr(logging, Config.LOG_LEVEL))
    
    # تنسيق الرسائل
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # تسجيل في ملف مع تدوير
    file_handler = RotatingFileHandler(
        Config.LOG_FILE,
        maxBytes=Config.LOG_MAX_SIZE,
        backupCount=Config.LOG_BACKUP_COUNT
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # تسجيل في الكونسول
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()

# ==================== utils/security.py ====================
import re
from typing import List, Set

def validate_page_range(range_str: str, total_pages: int) -> List[int]:
    """التحقق من صحة نطاق الصفحات"""
    if not range_str or not range_str.strip():
        raise ValueError("يجب إدخال نطاق الصفحات")
    
    range_str = range_str.replace(" ", "")
    pattern = r'^(\d+(-\d+)?)(,\d+(-\d+)?)*$'
    
    if not re.match(pattern, range_str):
        raise ValueError("تنسيق غير صحيح. استخدم مثلاً: 1-5 أو 1,3,5")
    
    pages: Set[int] = set()
    
    for part in range_str.split(','):
        if '-' in part:
            try:
                start, end = map(int, part.split('-'))
                if start < 1 or end > total_pages or start > end:
                    raise ValueError(f"نطاق {start}-{end} غير صحيح")
                pages.update(range(start, end + 1))
            except ValueError as e:
                raise ValueError(f"خطأ في النطاق: {e}")
        else:
            try:
                page = int(part)
                if page < 1 or page > total_pages:
                    raise ValueError(f"رقم الصفحة {page} غير موجود")
                pages.add(page)
            except ValueError:
                raise ValueError(f"'{part}' ليس رقماً صحيحاً")
    
    if not pages:
        raise ValueError("لم يتم تحديد أي صفحات صالحة")
    
    return sorted(pages)

def safe_filename(filename: str) -> str:
    """تنظيف اسم الملف من الأحرف الخطيرة"""
    return re.sub(r'[^\w\-_.]', '_', filename)

def validate_password(password: str) -> bool:
    """التحقق من قوة كلمة المرور"""
    if len(password) < 4:
        return False
    return True

# ==================== models/session.py ====================
from dataclasses import dataclass, field
from typing import List, Optional, Dict
import os
import shutil
from utils.logger import logger

@dataclass
class UserSession:
    """إدارة جلسة المستخدم"""
    user_id: int
    files: List[str] = field(default_factory=list)
    temp_dirs: List[str] = field(default_factory=list)
    action: Optional[str] = None
    val1: Optional[str] = None
    state: str = "IDLE"
    
    def add_file(self, file_path: str, temp_dir: str = None):
        """إضافة ملف مع مجلده المؤقت"""
        self.files.append(file_path)
        if temp_dir:
            self.temp_dirs.append(temp_dir)
    
    def cleanup(self):
        """تنظيف جميع الملفات والمجلدات المؤقتة"""
        for path in self.files:
            try:
                if os.path.isfile(path):
                    os.remove(path)
            except Exception as e:
                logger.warning(f"Failed to remove file {path}: {e}")
        
        for dir_path in self.temp_dirs:
            try:
                if os.path.isdir(dir_path):
                    shutil.rmtree(dir_path, ignore_errors=True)
            except Exception as e:
                logger.warning(f"Failed to remove dir {dir_path}: {e}")
        
        self.files.clear()
        self.temp_dirs.clear()
        self.val1 = None
    
    def reset(self):
        """إعادة تعيين الجلسة بالكامل"""
        self.cleanup()
        self.action = None
        self.state = "IDLE"

# ==================== utils/file_manager.py ====================
import tempfile
import shutil
from pathlib import Path
from typing import Tuple, Optional
from telegram import File
from config import Config
from utils.logger import logger

class FileManager:
    """مدير الملفات المؤقتة"""
    
    @staticmethod
    async def download_file(file: File, user_id: int, suffix: str = "") -> Tuple[str, str]:
        """تنزيل الملف مع إدارة المجلدات المؤقتة"""
        try:
            temp_dir = Path(tempfile.mkdtemp(dir=Config.TEMP_DIR))
            filename = f"file_{user_id}_{suffix}"
            file_path = temp_dir / filename
            
            await file.download_to_drive(str(file_path))
            logger.info(f"File downloaded: {file_path} for user {user_id}")
            
            return str(file_path), str(temp_dir)
        except Exception as e:
            logger.error(f"Error downloading file for user {user_id}: {e}")
            raise
    
    @staticmethod
    def cleanup_files(file_paths: list):
        """حذف آمن للملفات والمجلدات"""
        for path in file_paths:
            try:
                if os.path.isfile(path):
                    os.remove(path)
                elif os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
            except Exception as e:
                logger.warning(f"Cleanup failed for {path}: {e}")
    
    @staticmethod
    def get_temp_file(suffix: str = "") -> str:
        """إنشاء ملف مؤقت"""
        return tempfile.mktemp(suffix=suffix, dir=Config.TEMP_DIR)

# ==================== processors/pdf_processor.py ====================
import fitz
from pypdf import PdfReader, PdfWriter
from pypdf.errors import WrongPasswordError
from pypdf.generic import AnnotationBuilder
from PIL import Image
import zipfile
import io
from typing import List, Union
from utils.logger import logger
from config import Config

class PDFProcessor:
    """معالج عمليات PDF المتقدمة"""
    
    @staticmethod
    def merge_pdfs(file_paths: List[str]) -> str:
        """دمج ملفات PDF متعددة"""
        try:
            writer = PdfWriter()
            for f in file_paths:
                reader = PdfReader(f)
                for page in reader.pages:
                    writer.add_page(page)
            
            output_path = tempfile.mktemp(suffix=".pdf", dir=Config.TEMP_DIR)
            with open(output_path, "wb") as f:
                writer.write(f)
            
            logger.info(f"Merged {len(file_paths)} PDFs into {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Error merging PDFs: {e}")
            raise
    
    @staticmethod
    def images_to_pdf(image_paths: List[str]) -> str:
        """تحويل مجموعة صور إلى PDF"""
        try:
            images = [Image.open(path).convert("RGB") for path in image_paths]
            output_path = tempfile.mktemp(suffix=".pdf", dir=Config.TEMP_DIR)
            images[0].save(output_path, save_all=True, append_images=images[1:])
            
            logger.info(f"Converted {len(images)} images to PDF: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Error converting images to PDF: {e}")
            raise
    
    @staticmethod
    def extract_images_from_pdf(pdf_path: str) -> bytes:
        """استخراج الصور من PDF وإرجاعها كـ ZIP"""
        try:
            reader = PdfReader(pdf_path)
            zip_buffer = io.BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                for i, page in enumerate(reader.pages):
                    for j, img in enumerate(page.images):
                        ext = img.name.split(".")[-1] if "." in img.name else "jpg"
                        filename = f"صفحة_{i+1}_صورة_{j+1}.{ext}"
                        zf.writestr(filename, img.data)
            
            zip_buffer.seek(0)
            logger.info(f"Extracted images from {pdf_path}")
            return zip_buffer.getvalue()
        except Exception as e:
            logger.error(f"Error extracting images: {e}")
            raise
    
    @staticmethod
    def add_page_numbers(pdf_path: str) -> str:
        """إضافة أرقام للصفحات"""
        try:
            reader = PdfReader(pdf_path)
            writer = PdfWriter()
            
            for num, page in enumerate(reader.pages, start=1):
                # إضافة رقم في أسفل الصفحة
                watermark = AnnotationBuilder.text(
                    text=str(num),
                    xy=(250, 10),
                    font_size=14,
                    color=(0, 0, 0)
                ).get_page()
                page.merge_page(watermark)
                writer.add_page(page)
            
            output_path = tempfile.mktemp(suffix=".pdf", dir=Config.TEMP_DIR)
            with open(output_path, "wb") as f:
                writer.write(f)
            
            logger.info(f"Added page numbers to {pdf_path}")
            return output_path
        except Exception as e:
            logger.error(f"Error adding page numbers: {e}")
            raise
    
    @staticmethod
    def split_pdf_by_pages(pdf_path: str, pages: List[int]) -> str:
        """تقسيم PDF حسب الأرقام المحددة"""
        try:
            reader = PdfReader(pdf_path)
            writer = PdfWriter()
            
            for page_num in pages:
                if 0 <= page_num - 1 < len(reader.pages):
                    writer.add_page(reader.pages[page_num - 1])
            
            if len(writer.pages) == 0:
                raise ValueError("لم يتم تحديد أي صفحات صالحة")
            
            output_path = tempfile.mktemp(suffix=".pdf", dir=Config.TEMP_DIR)
            with open(output_path, "wb") as f:
                writer.write(f)
            
            logger.info(f"Split {pdf_path} by {len(pages)} pages")
            return output_path
        except Exception as e:
            logger.error(f"Error splitting PDF: {e}")
            raise
    
    @staticmethod
    def delete_pages(pdf_path: str, pages_to_delete: List[int]) -> str:
        """حذف صفحات محددة من PDF"""
        try:
            reader = PdfReader(pdf_path)
            writer = PdfWriter()
            
            pages_set = set(pages_to_delete)
            for num, page in enumerate(reader.pages, start=1):
                if num not in pages_set:
                    writer.add_page(page)
            
            output_path = tempfile.mktemp(suffix=".pdf", dir=Config.TEMP_DIR)
            with open(output_path, "wb") as f:
                writer.write(f)
            
            logger.info(f"Deleted {len(pages_to_delete)} pages from {pdf_path}")
            return output_path
        except Exception as e:
            logger.error(f"Error deleting pages: {e}")
            raise
    
    @staticmethod
    def rotate_pages(pdf_path: str, degrees: int) -> str:
        """تدوير صفحات PDF"""
        try:
            if degrees not in [90, 180, 270]:
                raise ValueError("الزاوية يجب أن تكون 90 أو 180 أو 270")
            
            reader = PdfReader(pdf_path)
            writer = PdfWriter()
            
            for page in reader.pages:
                page.rotate(degrees)
                writer.add_page(page)
            
            output_path = tempfile.mktemp(suffix=".pdf", dir=Config.TEMP_DIR)
            with open(output_path, "wb") as f:
                writer.write(f)
            
            logger.info(f"Rotated {pdf_path} by {degrees} degrees")
            return output_path
        except Exception as e:
            logger.error(f"Error rotating pages: {e}")
            raise
    
    @staticmethod
    def compress_pdf(pdf_path: str) -> str:
        """ضغط حجم PDF"""
        try:
            reader = PdfReader(pdf_path)
            writer = PdfWriter()
            
            for page in reader.pages:
                page.compress_content_streams()
                writer.add_page(page)
            
            output_path = tempfile.mktemp(suffix=".pdf", dir=Config.TEMP_DIR)
            with open(output_path, "wb") as f:
                writer.write(f)
            
            original_size = os.path.getsize(pdf_path)
            new_size = os.path.getsize(output_path)
            logger.info(f"Compressed {pdf_path}: {original_size} -> {new_size} bytes")
            
            return output_path
        except Exception as e:
            logger.error(f"Error compressing PDF: {e}")
            raise
    
    @staticmethod
    def pdf_to_images(pdf_path: str, dpi: int = 200) -> bytes:
        """تحويل PDF لصور مضغوطة في ZIP"""
        try:
            doc = fitz.open(pdf_path)
            zip_buffer = io.BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                for i, page in enumerate(doc):
                    pix = page.get_pixmap(dpi=dpi)
                    img_data = pix.tobytes("jpeg")
                    filename = f"صفحة_{i+1}.jpg"
                    zf.writestr(filename, img_data)
            
            doc.close()
            zip_buffer.seek(0)
            
            logger.info(f"Converted {pdf_path} to {i+1} images")
            return zip_buffer.getvalue()
        except Exception as e:
            logger.error(f"Error converting PDF to images: {e}")
            raise
    
    @staticmethod
    def add_watermark(pdf_path: str, text: str) -> str:
        """إضافة علامة مائية نصية"""
        try:
            reader = PdfReader(pdf_path)
            writer = PdfWriter()
            
            # إنشاء علامة مائية
            watermark = AnnotationBuilder.text(
                text=text,
                xy=(200, 400),
                font_size=30,
                color=(0, 0, 0, 0.3)  # شفافية 30%
            ).get_page()
            
            for page in reader.pages:
                page.merge_page(watermark)
                writer.add_page(page)
            
            output_path = tempfile.mktemp(suffix=".pdf", dir=Config.TEMP_DIR)
            with open(output_path, "wb") as f:
                writer.write(f)
            
            logger.info(f"Added watermark to {pdf_path}")
            return output_path
        except Exception as e:
            logger.error(f"Error adding watermark: {e}")
            raise
    
    @staticmethod
    def get_pdf_info(pdf_path: str) -> dict:
        """استخراج معلومات PDF"""
        try:
            reader = PdfReader(pdf_path)
            info = {
                "pages": len(reader.pages),
                "title": reader.metadata.title if reader.metadata else "غير محدد",
                "author": reader.metadata.author if reader.metadata else "غير محدد",
                "creator": reader.metadata.creator if reader.metadata else "غير محدد",
                "creation_date": reader.metadata.creation_date if reader.metadata else "غير محدد",
                "modification_date": reader.metadata.modification_date if reader.metadata else "غير محدد",
                "is_encrypted": reader.is_encrypted,
                "size": os.path.getsize(pdf_path)
            }
            return info
        except Exception as e:
            logger.error(f"Error getting PDF info: {e}")
            raise
    
    @staticmethod
    def reorder_pages(pdf_path: str, order: List[int]) -> str:
        """إعادة ترتيب صفحات PDF"""
        try:
            reader = PdfReader(pdf_path)
            writer = PdfWriter()
            
            for page_num in order:
                if 0 <= page_num - 1 < len(reader.pages):
                    writer.add_page(reader.pages[page_num - 1])
            
            output_path = tempfile.mktemp(suffix=".pdf", dir=Config.TEMP_DIR)
            with open(output_path, "wb") as f:
                writer.write(f)
            
            logger.info(f"Reordered pages of {pdf_path}")
            return output_path
        except Exception as e:
            logger.error(f"Error reordering pages: {e}")
            raise
    
    @staticmethod
    def encrypt_pdf(pdf_path: str, password: str) -> str:
        """تشفير PDF بكلمة مرور"""
        try:
            reader = PdfReader(pdf_path)
            writer = PdfWriter()
            
            for page in reader.pages:
                writer.add_page(page)
            
            writer.encrypt(password, password, algorithm="AES-256")
            
            output_path = tempfile.mktemp(suffix=".pdf", dir=Config.TEMP_DIR)
            with open(output_path, "wb") as f:
                writer.write(f)
            
            logger.info(f"Encrypted {pdf_path} with password")
            return output_path
        except Exception as e:
            logger.error(f"Error encrypting PDF: {e}")
            raise
    
    @staticmethod
    def decrypt_pdf(pdf_path: str, password: str) -> str:
        """فك تشفير PDF"""
        try:
            reader = PdfReader(pdf_path, password=password)
            if reader.is_encrypted:
                raise WrongPasswordError("كلمة المرور غير صحيحة")
            
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            
            output_path = tempfile.mktemp(suffix=".pdf", dir=Config.TEMP_DIR)
            with open(output_path, "wb") as f:
                writer.write(f)
            
            logger.info(f"Decrypted {pdf_path}")
            return output_path
        except WrongPasswordError:
            raise
        except Exception as e:
            logger.error(f"Error decrypting PDF: {e}")
            raise

# ==================== handlers/subscription.py ====================
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import Config
from utils.logger import logger

class SubscriptionHandler:
    """معالج الاشتراك في القناة"""
    
    @staticmethod
    async def check_subscription(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """التحقق من اشتراك المستخدم في القناة"""
        try:
            member = await context.bot.get_chat_member(
                chat_id=f"@{Config.CHANNEL_USERNAME}",
                user_id=user_id
            )
            return member.status in ["member", "administrator", "creator"]
        except Exception as e:
            logger.warning(f"Subscription check failed for user {user_id}: {e}")
            return False
    
    @staticmethod
    def get_subscription_keyboard():
        """الحصول على لوحة مفاتيح الاشتراك"""
        keyboard = [
            [
                InlineKeyboardButton(
                    "🔗 اشترك في القناة",
                    url=f"https://t.me/{Config.CHANNEL_USERNAME}"
                )
            ],
            [
                InlineKeyboardButton(
                    "✅ تحقق من الاشتراك",
                    callback_data="check_sub"
                )
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

# ==================== handlers/action_handler.py ====================
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from models.session import UserSession
from processors.pdf_processor import PDFProcessor
from utils.security import validate_page_range, validate_password
from utils.file_manager import FileManager
from utils.logger import logger
from config import Config

class ActionHandler:
    """معالج إجراءات البوت"""
    
    # لوحات المفاتيح
    MAIN_KEYBOARD = [
        ["📎 دمج ملفات PDF", "🖼️ تحويل صور لـ PDF"],
        ["📸 استخراج صور من PDF", "🔢 ترقيم صفحات PDF"],
        ["✂️ تقسيم PDF", "🗑️ حذف صفحات من PDF"],
        ["📄 استخراج صفحات من PDF", "🔄 تدوير صفحات PDF"],
        ["📉 ضغط حجم PDF", "🖼️ تحويل PDF لصور"],
        ["💧 علامة مائية", "ℹ️ معلومات الملف"],
        ["🔃 إعادة ترتيب", "🔒 حماية بكلمة مرور"],
        ["🔓 إزالة الحماية", "🧹 مسح الملفات"]
    ]
    
    MAIN_MARKUP = ReplyKeyboardMarkup(MAIN_KEYBOARD, resize_keyboard=True)
    ACTION_MARKUP = ReplyKeyboardMarkup(
        [["✅ إنهاء وإجراء العملية", "➕ إضافة ملفات أخرى"]],
        resize_keyboard=True
    )
    
    # رسائل الإرشاد
    PROMPTS = {
        "📎 دمج ملفات PDF": "📤 أرسل ملفات PDF واحدة تلو الأخرى، ثم اختر 'إنهاء'",
        "🖼️ تحويل صور لـ PDF": "🖼️ أرسل الصور واحدة تلو الأخرى، ثم اختر 'إنهاء'",
        "📸 استخراج صور من PDF": "📄 أرسل ملف PDF لاستخراج صوره",
        "🔢 ترقيم صفحات PDF": "📄 أرسل ملف PDF لإضافة أرقام الصفحات",
        "✂️ تقسيم PDF": "📄 أرسل ملف PDF، ثم اكتب نطاق التقسيم (مثال: 1-5 أو 3,7,9)",
        "🗑️ حذف صفحات من PDF": "📄 أرسل ملف PDF، ثم اكتب أرقام الصفحات المراد حذفها (مثال: 2,4,6)",
        "📄 استخراج صفحات من PDF": "📄 أرسل ملف PDF، ثم اكتب أرقام الصفحات (مثال: 1-3,5)",
        "🔄 تدوير صفحات PDF": "📄 أرسل ملف PDF، ثم اكتب الزاوية (90 / 180 / 270)",
        "📉 ضغط حجم PDF": "📄 أرسل ملف PDF لتقليل حجمه",
        "🖼️ تحويل PDF لصور": "📄 أرسل ملف PDF لتحويل صفحاته لصور",
        "💧 علامة مائية": "📄 أرسل ملف PDF، ثم اكتب النص للعلامة المائية",
        "ℹ️ معلومات الملف": "📄 أرسل ملف PDF لعرض تفاصيله",
        "🔃 إعادة ترتيب": "📄 أرسل ملف PDF، ثم اكتب الترتيب الجديد (مثال: 3,1,2,4)",
        "🔒 حماية بكلمة مرور": "📄 أرسل ملف PDF، ثم اكتب كلمة المرور",
        "🔓 إزالة الحماية": "📄 أرسل ملف PDF المحمي، ثم اكتب كلمة المرور",
        "🧹 مسح الملفات": "✅ تم مسح جميع الملفات المؤقتة"
    }
    
    def __init__(self, sessions: dict):
        self.sessions = sessions
    
    async def handle_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة اختيار الإجراء"""
        user_id = update.effective_user.id
        action = update.message.text
        
        # إنشاء جلسة جديدة إذا لم تكن موجودة
        if user_id not in self.sessions:
            self.sessions[user_id] = UserSession(user_id=user_id)
        
        session = self.sessions[user_id]
        session.action = action
        
        # معالجة مسح الملفات
        if action == "🧹 مسح الملفات":
            session.cleanup()
            await update.message.reply_text(
                self.PROMPTS[action],
                reply_markup=self.MAIN_MARKUP
            )
            return "SELECT_ACTION"
        
        # إرسال رسالة الإرشاد
        await update.message.reply_text(
            self.PROMPTS.get(action, "اختر الميزة المطلوبة"),
            reply_markup=ReplyKeyboardRemove()
        )
        
        return "WAIT_FILE"
    
    async def receive_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """استقبال الملفات من المستخدم"""
        user_id = update.effective_user.id
        session = self.sessions.get(user_id)
        
        if not session or not session.action:
            await update.message.reply_text(
                "❌ يرجى اختيار إجراء أولاً",
                reply_markup=self.MAIN_MARKUP
            )
            return "SELECT_ACTION"
        
        text = update.message.text
        
        # معالجة الأزرار
        if text == "✅ إنهاء وإجراء العملية":
            return await self.process_action(update, context)
        
        if text == "➕ إضافة ملفات أخرى":
            await update.message.reply_text(
                "✅ تابع إرسال الملفات، ثم اختر 'إنهاء' عند الانتهاء"
            )
            return "WAIT_FILE"
        
        # معالجة الملفات
        if update.message.document:
            return await self.handle_document(update, context, session)
        
        elif update.message.photo:
            return await self.handle_photo(update, context, session)
        
        # معالجة النصوص (الأرقام، كلمات المرور، إلخ)
        elif text:
            session.val1 = text.strip()
            return await self.process_action(update, context)
        
        await update.message.reply_text("❌ يرجى إرسال ملف أو نص صحيح")
        return "WAIT_FILE"
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession):
        """معالجة الملفات المستلمة"""
        doc = update.message.document
        
        # التحقق من الحجم
        if doc.file_size > Config.MAX_FILE_SIZE:
            await update.message.reply_text(
                f"❌ حجم الملف كبير جداً! الحد الأقصى {Config.MAX_FILE_SIZE // (1024*1024)} ميجابايت"
            )
            return "WAIT_FILE"
        
        # التحقق من الصيغة
        if "PDF" in session.action and not doc.file_name.lower().endswith(".pdf"):
            await update.message.reply_text("❌ أرسل ملف بصيغة PDF فقط!")
            return "WAIT_FILE"
        
        # تنزيل الملف
        try:
            file = await context.bot.get_file(doc.file_id)
            file_path, temp_dir = await FileManager.download_file(
                file, 
                session.user_id, 
                f"_{len(session.files)}"
            )
            session.add_file(file_path, temp_dir)
            
            await update.message.reply_text(
                f"✅ تم استلام الملف: {doc.file_name}\n"
                f"📦 عدد الملفات: {len(session.files)}",
                reply_markup=self.ACTION_MARKUP
            )
            
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            await update.message.reply_text("❌ حدث خطأ في تحميل الملف")
        
        return "WAIT_FILE"
    
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession):
        """معالجة الصور المستلمة"""
        photo = update.message.photo[-1]
        
        if photo.file_size > Config.MAX_FILE_SIZE:
            await update.message.reply_text("❌ حجم الصورة كبير جداً!")
            return "WAIT_FILE"
        
        try:
            file = await context.bot.get_file(photo.file_id)
            file_path, temp_dir = await FileManager.download_file(
                file,
                session.user_id,
                f"_img_{len(session.files)}.jpg"
            )
            session.add_file(file_path, temp_dir)
            
            await update.message.reply_text(
                f"✅ تم استلام الصورة {len(session.files)}",
                reply_markup=self.ACTION_MARKUP
            )
            
        except Exception as e:
            logger.error(f"Error downloading photo: {e}")
            await update.message.reply_text("❌ حدث خطأ في تحميل الصورة")
        
        return "WAIT_FILE"
    
    async def process_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """تنفيذ الإجراء المطلوب"""
        user_id = update.effective_user.id
        session = self.sessions.get(user_id)
        
        if not session or not session.files:
            await update.message.reply_text(
                "❌ لم يتم إرسال أي ملف!",
                reply_markup=self.MAIN_MARKUP
            )
            return "SELECT_ACTION"
        
        try:
            result = await self._execute_action(session, update)
            
            if result:
                await self._send_result(update, result, session)
            
        except Exception as e:
            logger.error(f"Error processing action: {e}")
            await update.message.reply_text(
                f"❌ حدث خطأ: {str(e)[:150]}",
                reply_markup=self.MAIN_MARKUP
            )
        
        finally:
            session.cleanup()
            session.action = None
        
        return "SELECT_ACTION"
    
    async def _execute_action(self, session: UserSession, update: Update):
        """تنفيذ الإجراء الفعلي"""
        action = session.action
        files = session.files
        val1 = session.val1
        
        if action == "📎 دمج ملفات PDF":
            if len(files) < 2:
                raise ValueError("يجب إرسال ملفين على الأقل")
            return {
                "file": PDFProcessor.merge_pdfs(files),
                "name": "ملفات_مدمجة.pdf",
                "caption": f"✅ تم دمج {len(files)} ملف بنجاح"
            }
        
        elif action == "🖼️ تحويل صور لـ PDF":
            return {
                "file": PDFProcessor.images_to_pdf(files),
                "name": "صور_محولة_لـ_PDF.pdf",
                "caption": f"✅ تم تحويل {len(files)} صورة لـ PDF"
            }
        
        elif action == "📸 استخراج صور من PDF":
            zip_data = PDFProcessor.extract_images_from_pdf(files[0])
            temp_file = FileManager.get_temp_file(".zip")
            with open(temp_file, "wb") as f:
                f.write(zip_data)
            return {
                "file": temp_file,
                "name": "صور_مستخرجة.zip",
                "caption": "✅ تم استخراج الصور بنجاح"
            }
        
        elif action == "🔢 ترقيم صفحات PDF":
            return {
                "file": PDFProcessor.add_page_numbers(files[0]),
                "name": "ملف_مرقم_الصفحات.pdf",
                "caption": "✅ تم ترقيم الصفحات بنجاح"
            }
        
        elif action in ["✂️ تقسيم PDF", "📄 استخراج صفحات من PDF"]:
            if not val1:
                raise ValueError("يرجى إدخال نطاق الصفحات")
            reader = PdfReader(files[0])
            pages = validate_page_range(val1, len(reader.pages))
            return {
                "file": PDFProcessor.split_pdf_by_pages(files[0], pages),
                "name": "ملف_مقسم.pdf",
                "caption": f"✅ تم استخراج {len(pages)} صفحة بنجاح"
            }
        
        elif action == "🗑️ حذف صفحات من PDF":
            if not val1:
                raise ValueError("يرجى إدخال أرقام الصفحات للحذف")
            reader = PdfReader(files[0])
            pages = validate_page_range(val1, len(reader.pages))
            return {
                "file": PDFProcessor.delete_pages(files[0], pages),
                "name": "ملف_بعد_حذف_الصفحات.pdf",
                "caption": f"✅ تم حذف {len(pages)} صفحة بنجاح"
            }
        
        elif action == "🔄 تدوير صفحات PDF":
            if not val1:
                raise ValueError("يرجى إدخال زاوية التدوير")
            degrees = int(val1)
            return {
                "file": PDFProcessor.rotate_pages(files[0], degrees),
                "name": "ملف_مدور.pdf",
                "caption": f"✅ تم تدوير الصفحات بزاوية {degrees}°"
            }
        
        elif action == "📉 ضغط حجم PDF":
            return {
                "file": PDFProcessor.compress_pdf(files[0]),
                "name": "ملف_مضغوط.pdf",
                "caption": "✅ تم ضغط الملف بنجاح"
            }
        
        elif action == "🖼️ تحويل PDF لصور":
            zip_data = PDFProcessor.pdf_to_images(files[0])
            temp_file = FileManager.get_temp_file(".zip")
            with open(temp_file, "wb") as f:
                f.write(zip_data)
            return {
                "file": temp_file,
                "name": "صفحات_محولة_لصور.zip",
                "caption": "✅ تم تحويل PDF لصور بنجاح"
            }
        
        elif action == "💧 علامة مائية":
            if not val1:
                raise ValueError("يرجى إدخال نص العلامة المائية")
            return {
                "file": PDFProcessor.add_watermark(files[0], val1),
                "name": "ملف_بعلامة_مائية.pdf",
                "caption": f"✅ تم إضافة العلامة المائية: '{val1}'"
            }
        
        elif action == "ℹ️ معلومات الملف":
            info = PDFProcessor.get_pdf_info(files[0])
            message = (
                f"📄 **معلومات الملف:**\n\n"
                f"📊 عدد الصفحات: `{info['pages']}`\n"
                f"📝 العنوان: `{info['title']}`\n"
                f"✍️ المؤلف: `{info['author']}`\n"
                f"🖥️ البرنامج: `{info['creator']}`\n"
                f"📅 تاريخ الإنشاء: `{info['creation_date']}`\n"
                f"🔄 تاريخ التعديل: `{info['modification_date']}`\n"
                f"🔒 محمي: `{'نعم' if info['is_encrypted'] else 'لا'}`\n"
                f"📦 الحجم: `{info['size'] // 1024} كيلوبايت`"
            )
            await update.message.reply_text(message, reply_markup=self.MAIN_MARKUP)
            return None
        
        elif action == "🔃 إعادة ترتيب":
            if not val1:
                raise ValueError("يرجى إدخال الترتيب الجديد")
            order = list(map(int, val1.replace(" ", "").split(",")))
            return {
                "file": PDFProcessor.reorder_pages(files[0], order),
                "name": "ملف_معاد_الترتيب.pdf",
                "caption": f"✅ تم إعادة ترتيب الصفحات: {val1}"
            }
        
        elif action == "🔒 حماية بكلمة مرور":
            if not val1:
                raise ValueError("يرجى إدخال كلمة المرور")
            if not validate_password(val1):
                raise ValueError("كلمة المرور يجب أن تكون 4 أحرف على الأقل")
            return {
                "file": PDFProcessor.encrypt_pdf(files[0], val1),
                "name": "ملف_محمي.pdf",
                "caption": "✅ تم حماية الملف بكلمة مرور"
            }
        
        elif action == "🔓 إزالة الحماية":
            if not val1:
                raise ValueError("يرجى إدخال كلمة المرور")
            return {
                "file": PDFProcessor.decrypt_pdf(files[0], val1),
                "name": "ملف_بدون_حماية.pdf",
                "caption": "✅ تم إزالة الحماية بنجاح"
            }
        
        else:
            raise ValueError(f"إجراء غير معروف: {action}")
    
    async def _send_result(self, update: Update, result: dict, session: UserSession):
        """إرسال نتيجة العملية"""
        if not result:
            return
        
        try:
            with open(result["file"], "rb") as f:
                await update.message.reply_document(
                    document=f,
                    filename=result["name"],
                    caption=result.get("caption", "✅ تمت العملية بنجاح"),
                    reply_markup=self.MAIN_MARKUP
                )
        except Exception as e:
            logger.error(f"Error sending result: {e}")
            raise
        finally:
            if os.path.exists(result["file"]):
                try:
                    os.remove(result["file"])
                except:
                    pass

# ==================== main.py ====================
import warnings
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler
)
from telegram.warnings import PTBUserWarning
from config import Config
from handlers.subscription import SubscriptionHandler
from handlers.action_handler import ActionHandler
from utils.logger import logger

# إخفاء التحذيرات
warnings.filterwarnings(action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning)

# حالات المحادثة
CHECK_SUB, SELECT_ACTION, WAIT_FILE = range(3)

# تخزين الجلسات
user_sessions = {}

class PDFBot:
    """البوت الرئيسي"""
    
    def __init__(self):
        self.subscription_handler = SubscriptionHandler()
        self.action_handler = ActionHandler(user_sessions)
        self.app = None
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالج أمر /start"""
        user_id = update.effective_user.id
        
        # تنظيف الجلسة القديمة
        if user_id in user_sessions:
            user_sessions[user_id].reset()
        
        # التحقق من الاشتراك
        if not await self.subscription_handler.check_subscription(user_id, context):
            keyboard = self.subscription_handler.get_subscription_keyboard()
            await update.message.reply_text(
                "⚠️ **للاستفادة من البوت يجب الاشتراك في القناة أولاً**\n\n"
                "🔔 بعد الاشتراك، اضغط على زر التحقق",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            return CHECK_SUB
        
        # بدء الجلسة
        await update.message.reply_text(
            "👋 **مرحباً بك في البوت الشامل لملفات PDF!**\n\n"
            "📚 اختر الميزة التي تريدها من القائمة أدناه 👇",
            reply_markup=self.action_handler.MAIN_MARKUP,
            parse_mode="Markdown"
        )
        return SELECT_ACTION
    
    async def verify_subscription_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالج التحقق من الاشتراك"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if await self.subscription_handler.check_subscription(user_id, context):
            await query.edit_message_text(
                "✅ **تم التحقق من اشتراكك!**\n\n"
                "🎉 يمكنك الآن استخدام جميع ميزات البوت"
            )
            await query.message.reply_text(
                "📚 اختر الميزة التي تريدها:",
                reply_markup=self.action_handler.MAIN_MARKUP
            )
            return SELECT_ACTION
        else:
            await query.answer(
                "❌ لم يتم العثور على اشتراكك!\n"
                "يرجى الاشتراك في القناة ثم التحقق مرة أخرى",
                show_alert=True
            )
            return CHECK_SUB
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """إلغاء العملية الحالية"""
        user_id = update.effective_user.id
        if user_id in user_sessions:
            user_sessions[user_id].reset()
        
        await update.message.reply_text(
            "❌ تم إلغاء العملية",
            reply_markup=self.action_handler.MAIN_MARKUP
        )
        return SELECT_ACTION
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالج الأخطاء المركزي"""
        logger.error(f"Update {update} caused error {context.error}")
        
        try:
            if update and update.effective_message:
                await update.effective_message.reply_text(
                    "❌ حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى.",
                    reply_markup=self.action_handler.MAIN_MARKUP
                )
        except Exception as e:
            logger.error(f"Error in error handler: {e}")
    
    def build_app(self):
        """بناء تطبيق البوت"""
        self.app = ApplicationBuilder().token(Config.BOT_TOKEN).build()
        
        # إعداد محادثة
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", self.start)],
            states={
                CHECK_SUB: [
                    CallbackQueryHandler(self.verify_subscription_callback, pattern="check_sub")
                ],
                SELECT_ACTION: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.action_handler.handle_action
                    )
                ],
                WAIT_FILE: [
                    MessageHandler(
                        filters.ALL & ~filters.COMMAND,
                        self.action_handler.receive_file
                    )
                ]
            },
            fallbacks=[
                CommandHandler("start", self.start),
                CommandHandler("cancel", self.cancel)
            ],
            per_chat=True,
            per_user=True,
            per_message=False
        )
        
        self.app.add_handler(conv_handler)
        
        # إضافة معالج الأخطاء
        self.app.add_error_handler(self.error_handler)
        
        return self.app
    
    def run(self):
        """تشغيل البوت"""
        if not Config.BOT_TOKEN:
            logger.error("BOT_TOKEN not found in environment variables!")
            return
        
        Config.ensure_directories()
        
        self.build_app()
        logger.info("🚀 PDF Bot is running...")
        
        try:
            self.app.run_polling(drop_pending_updates=True)
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Bot crashed: {e}")

# ==================== __main__ ====================
if __name__ == "__main__":
    bot = PDFBot()
    bot.run()

import os
import io
import zipfile
from pathlib import Path
from typing import List, Tuple, Optional
from PIL import Image
from pypdf import PdfReader, PdfWriter
import fitz
from config import Config
from utils import logger, format_size, safe_remove

class PDFEngine:
    
    @staticmethod
    def get_metadata(path: str) -> dict:
        """استخراج بيانات الملف"""
        try:
            reader = PdfReader(path)
            meta = reader.metadata or {}
            return {
                "pages": len(reader.pages),
                "title": meta.get("/Title", "غير محدد") or "غير محدد",
                "author": meta.get("/Author", "غير محدد") or "غير محدد",
                "creator": meta.get("/Creator", "غير محدد") or "غير محدد",
                "encrypted": reader.is_encrypted,
                "size": os.path.getsize(path)
            }
        except Exception as e:
            logger.error(f"خطأ في قراءة بيانات الملف: {e}")
            return {"pages": 0, "title": "خطأ", "author": "خطأ", "encrypted": False, "size": 0}

    @staticmethod
    def merge(pdf_paths: List[str]) -> str:
        """دمج ملفات PDF"""
        if not pdf_paths:
            raise ValueError("لا توجد ملفات للدمج")
            
        writer = PdfWriter()
        for path in pdf_paths:
            try:
                reader = PdfReader(path)
                for page in reader.pages:
                    writer.add_page(page)
            except Exception as e:
                raise ValueError(f"خطأ في قراءة الملف {Path(path).name}: {e}")
        
        out_path = Path(Config.TEMP_DIR) / f"merge_{os.urandom(4).hex()}.pdf"
        with open(out_path, "wb") as f:
            writer.write(f)
        return str(out_path)

    @staticmethod
    def add_page_numbers(pdf_path: str) -> str:
        """إضافة أرقام صفحات"""
        try:
            doc = fitz.open(pdf_path)
            
            for i, page in enumerate(doc, 1):
                rect = fitz.Rect(460, page.rect.height - 40, 550, page.rect.height - 10)
                page.insert_textbox(
                    rect,
                    str(i),
                    fontsize=12,
                    color=(0, 0, 0),
                    align=fitz.TEXT_ALIGN_CENTER
                )
            
            out_path = Path(Config.TEMP_DIR) / f"numbered_{os.urandom(4).hex()}.pdf"
            doc.save(str(out_path))
            doc.close()
            return str(out_path)
            
        except Exception as e:
            logger.error(f"خطأ في إضافة الأرقام: {e}")
            raise ValueError(f"فشل إضافة الأرقام: {str(e)}")

    @staticmethod
    def add_watermark(pdf_path: str, text: str) -> str:
        """إضافة علامة مائية - تم إصلاح مشكلة الزاوية"""
        if not text:
            text = "© جميع الحقوق محفوظة"
            
        try:
            doc = fitz.open(pdf_path)
            
            for page in doc:
                rect = page.rect
                # ✅ استخدم insert_textbox مع زاوية 0 (بدون دوران) لتجنب خطأ rotate
                page.insert_textbox(
                    fitz.Rect(
                        rect.width * 0.2, 
                        rect.height * 0.4, 
                        rect.width * 0.8, 
                        rect.height * 0.6
                    ),
                    text,
                    fontsize=36,
                    color=(0.5, 0.5, 0.5, 0.3),
                    align=fitz.TEXT_ALIGN_CENTER
                )
                
                # ✅ إضافة علامة مائية ثانية في الزاوية السفلية
                page.insert_textbox(
                    fitz.Rect(
                        rect.width * 0.05, 
                        rect.height * 0.88, 
                        rect.width * 0.95, 
                        rect.height * 0.95
                    ),
                    text,
                    fontsize=14,
                    color=(0.7, 0.7, 0.7, 0.5),
                    align=fitz.TEXT_ALIGN_CENTER
                )
            
            out_path = Path(Config.TEMP_DIR) / f"watermarked_{os.urandom(4).hex()}.pdf"
            doc.save(str(out_path))
            doc.close()
            return str(out_path)
            
        except Exception as e:
            logger.error(f"خطأ في إضافة العلامة المائية: {e}")
            raise ValueError(f"فشل إضافة العلامة المائية: {str(e)}")

    @staticmethod
    def encrypt(pdf_path: str, password: str) -> str:
        """تشفير PDF بكلمة مرور - تم إصلاح مشكلة PERMISSIONS_ALL"""
        if not password or len(password) < 4:
            raise ValueError("كلمة المرور يجب أن تكون 4 أحرف على الأقل")
            
        try:
            reader = PdfReader(pdf_path)
            writer = PdfWriter()
            
            for page in reader.pages:
                writer.add_page(page)
            
            # ✅ استخدام الطريقة الصحيحة للتشفير في pypdf 5.0.1
            writer.encrypt(password)
            
            out_path = Path(Config.TEMP_DIR) / f"encrypted_{os.urandom(4).hex()}.pdf"
            with open(out_path, "wb") as f:
                writer.write(f)
            return str(out_path)
            
        except Exception as e:
            logger.error(f"خطأ في التشفير: {e}")
            raise ValueError(f"فشل تشفير الملف: {str(e)}")

    @staticmethod
    def compress(pdf_path: str) -> Tuple[str, int, int]:
        """ضغط ملف PDF - تم إصلاح مشكلة الضغط"""
        try:
            before = os.path.getsize(pdf_path)
            
            # ✅ طريقة الضغط الصحيحة باستخدام PyMuPDF (fitz)
            doc = fitz.open(pdf_path)
            
            # حفظ الملف بضغط عالي
            out_path = Path(Config.TEMP_DIR) / f"compressed_{os.urandom(4).hex()}.pdf"
            
            # ✅ استخدام save مع خيارات الضغط
            doc.save(
                str(out_path),
                garbage=4,           # تنظيف عميق
                deflate=True,        # ضغط
                clean=True,          # تنظيف البيانات غير المستخدمة
                no_encrypt=True
            )
            doc.close()
            
            after = os.path.getsize(out_path)
            
            # إذا كان الضغط أكبر من الأصلي، استخدم الأصلي
            if after > before:
                safe_remove(str(out_path))
                return pdf_path, before, before
                
            return str(out_path), before, after
            
        except Exception as e:
            logger.error(f"خطأ في الضغط: {e}")
            raise ValueError(f"فشل ضغط الملف: {str(e)}")

    @staticmethod
    def images_to_pdf(image_paths: List[str]) -> str:
        """تحويل الصور إلى PDF"""
        if not image_paths:
            raise ValueError("لا توجد صور للتحويل")
            
        try:
            images = []
            for path in image_paths:
                try:
                    img = Image.open(path)
                    if img.mode in ('RGBA', 'LA', 'P'):
                        img = img.convert('RGB')
                    images.append(img)
                except Exception as e:
                    raise ValueError(f"خطأ في قراءة الصورة {Path(path).name}: {e}")
            
            out_path = Path(Config.TEMP_DIR) / f"images_{os.urandom(4).hex()}.pdf"
            
            if len(images) == 1:
                images[0].save(str(out_path), "PDF", resolution=100.0)
            else:
                images[0].save(
                    str(out_path),
                    "PDF",
                    save_all=True,
                    append_images=images[1:],
                    resolution=100.0
                )
            
            for img in images:
                img.close()
                
            return str(out_path)
            
        except Exception as e:
            logger.error(f"خطأ في تحويل الصور: {e}")
            raise ValueError(f"فشل تحويل الصور: {str(e)}")

    @staticmethod
    def pdf_to_images(pdf_path: str, dpi: int = 150) -> Tuple[bytes, str]:
        """استخراج الصور من PDF"""
        try:
            doc = fitz.open(pdf_path)
            
            if len(doc) == 0:
                raise ValueError("الملف فارغ ولا يحتوي على صفحات")
                
            if len(doc) == 1:
                page = doc[0]
                pix = page.get_pixmap(dpi=dpi)
                img_data = pix.tobytes("jpeg")
                doc.close()
                return img_data, "صفحة_1.jpg"
            
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for i, page in enumerate(doc, 1):
                    pix = page.get_pixmap(dpi=dpi)
                    img_data = pix.tobytes("jpeg")
                    zf.writestr(f"صفحة_{i}.jpg", img_data)
            
            doc.close()
            return buf.getvalue(), "صور_مستخرجة.zip"
            
        except Exception as e:
            logger.error(f"خطأ في استخراج الصور: {e}")
            raise ValueError(f"فشل استخراج الصور: {str(e)}")

    @staticmethod
    def delete_pages(pdf_path: str, pages_to_delete: List[int]) -> str:
        """حذف صفحات محددة من PDF"""
        try:
            reader = PdfReader(pdf_path)
            total_pages = len(reader.pages)
            writer = PdfWriter()
            
            delete_set = set(pages_to_delete)
            
            for i in range(total_pages):
                if (i + 1) not in delete_set:
                    writer.add_page(reader.pages[i])
            
            if len(writer.pages) == 0:
                raise ValueError("لا يمكن حذف جميع الصفحات")
                
            out_path = Path(Config.TEMP_DIR) / f"deleted_{os.urandom(4).hex()}.pdf"
            with open(out_path, "wb") as f:
                writer.write(f)
            return str(out_path)
            
        except Exception as e:
            logger.error(f"خطأ في حذف الصفحات: {e}")
            raise ValueError(f"فشل حذف الصفحات: {str(e)}")

    @staticmethod
    def extract_pages(pdf_path: str, page_range: List[int]) -> str:
        """استخراج صفحات محددة من PDF"""
        try:
            reader = PdfReader(pdf_path)
            writer = PdfWriter()
            
            for page_num in page_range:
                if 1 <= page_num <= len(reader.pages):
                    writer.add_page(reader.pages[page_num - 1])
            
            if len(writer.pages) == 0:
                raise ValueError("لم يتم تحديد أي صفحات صالحة")
                
            out_path = Path(Config.TEMP_DIR) / f"extracted_{os.urandom(4).hex()}.pdf"
            with open(out_path, "wb") as f:
                writer.write(f)
            return str(out_path)
            
        except Exception as e:
            logger.error(f"خطأ في استخراج الصفحات: {e}")
            raise ValueError(f"فشل استخراج الصفحات: {str(e)}")
    
    @staticmethod
    def remove_password(pdf_path: str) -> str:
        """إزالة كلمة المرور من PDF"""
        try:
            reader = PdfReader(pdf_path)
            
            # التحقق مما إذا كان الملف مشفراً
            if not reader.is_encrypted:
                raise ValueError("الملف غير مشفر")
            
            # محاولة فك التشفير (بدون كلمة مرور)
            try:
                reader.decrypt('')
            except:
                raise ValueError("الملف مشفر بكلمة مرور غير معروفة")
            
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            
            out_path = Path(Config.TEMP_DIR) / f"unlocked_{os.urandom(4).hex()}.pdf"
            with open(out_path, "wb") as f:
                writer.write(f)
            return str(out_path)
            
        except Exception as e:
            logger.error(f"خطأ في إزالة الحماية: {e}")
            raise ValueError(f"فشل إزالة الحماية: {str(e)}")

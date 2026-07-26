import os
import io
import zipfile
from pathlib import Path
from typing import List, Tuple
from PIL import Image
from pypdf import PdfReader, PdfWriter
import fitz
from config import Config
from utils import logger, safe_remove

class PDFEngine:
    
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
                raise ValueError(f"خطأ في قراءة الملف: {e}")
        out_path = Path(Config.TEMP_DIR) / f"merge_{os.urandom(4).hex()}.pdf"
        with open(out_path, "wb") as f:
            writer.write(f)
        return str(out_path)

    @staticmethod
    def images_to_pdf(image_paths: List[str]) -> str:
        """تحويل الصور إلى PDF"""
        if not image_paths:
            raise ValueError("لا توجد صور للتحويل")
        try:
            images = []
            for path in image_paths:
                img = Image.open(path)
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                images.append(img)
            out_path = Path(Config.TEMP_DIR) / f"images_{os.urandom(4).hex()}.pdf"
            if len(images) == 1:
                images[0].save(str(out_path), "PDF")
            else:
                images[0].save(str(out_path), "PDF", save_all=True, append_images=images[1:])
            for img in images:
                img.close()
            return str(out_path)
        except Exception as e:
            raise ValueError(f"فشل تحويل الصور: {str(e)}")

    @staticmethod
    def pdf_to_images(pdf_path: str, dpi: int = 150) -> Tuple[bytes, str]:
        """استخراج الصور من PDF"""
        try:
            doc = fitz.open(pdf_path)
            if len(doc) == 0:
                raise ValueError("الملف فارغ")
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
            raise ValueError(f"فشل استخراج الصور: {str(e)}")

    @staticmethod
    def add_page_numbers(pdf_path: str) -> str:
        """إضافة أرقام صفحات"""
        try:
            doc = fitz.open(pdf_path)
            for i, page in enumerate(doc, 1):
                rect = fitz.Rect(
                    page.rect.width * 0.45,
                    page.rect.height - 40,
                    page.rect.width * 0.55,
                    page.rect.height - 10
                )
                page.insert_textbox(
                    rect,
                    str(i),
                    fontsize=14,
                    color=(0, 0, 0),
                    align=fitz.TEXT_ALIGN_CENTER
                )
            out_path = Path(Config.TEMP_DIR) / f"numbered_{os.urandom(4).hex()}.pdf"
            doc.save(str(out_path))
            doc.close()
            return str(out_path)
        except Exception as e:
            raise ValueError(f"فشل إضافة الأرقام: {str(e)}")

    @staticmethod
    def compress(pdf_path: str) -> Tuple[str, int, int]:
        """ضغط ملف PDF"""
        try:
            before = os.path.getsize(pdf_path)
            doc = fitz.open(pdf_path)
            out_path = Path(Config.TEMP_DIR) / f"compressed_{os.urandom(4).hex()}.pdf"
            doc.save(str(out_path), garbage=4, deflate=True, clean=True)
            doc.close()
            after = os.path.getsize(out_path)
            if after >= before:
                safe_remove(str(out_path))
                return pdf_path, before, before
            return str(out_path), before, after
        except Exception as e:
            raise ValueError(f"فشل ضغط الملف: {str(e)}")

    @staticmethod
    def encrypt(pdf_path: str, password: str) -> str:
        """تشفير PDF"""
        if not password or len(password) < 4:
            raise ValueError("كلمة المرور يجب أن تكون 4 أحرف على الأقل")
        try:
            reader = PdfReader(pdf_path)
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            writer.encrypt(password)
            out_path = Path(Config.TEMP_DIR) / f"encrypted_{os.urandom(4).hex()}.pdf"
            with open(out_path, "wb") as f:
                writer.write(f)
            return str(out_path)
        except Exception as e:
            raise ValueError(f"فشل تشفير الملف: {str(e)}")

    @staticmethod
    def remove_password(pdf_path: str) -> str:
        """إزالة كلمة المرور"""
        try:
            reader = PdfReader(pdf_path)
            if not reader.is_encrypted:
                raise ValueError("الملف غير مشفر")
            try:
                reader.decrypt('')
            except Exception:
                raise ValueError("لا يمكن إزالة الحماية بدون كلمة المرور")
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            out_path = Path(Config.TEMP_DIR) / f"unlocked_{os.urandom(4).hex()}.pdf"
            with open(out_path, "wb") as f:
                writer.write(f)
            return str(out_path)
        except Exception as e:
            raise ValueError(f"فشل إزالة الحماية: {str(e)}")

    @staticmethod
    def delete_pages(pdf_path: str, pages_to_delete: List[int]) -> str:
        """حذف صفحات محددة"""
        try:
            reader = PdfReader(pdf_path)
            total_pages = len(reader.pages)
            if total_pages == 0:
                raise ValueError("الملف فارغ")
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
            raise ValueError(f"فشل حذف الصفحات: {str(e)}")

    @staticmethod
    def extract_pages(pdf_path: str, page_range: List[int]) -> str:
        """استخراج صفحات محددة"""
        try:
            reader = PdfReader(pdf_path)
            total_pages = len(reader.pages)
            if total_pages == 0:
                raise ValueError("الملف فارغ")
            writer = PdfWriter()
            for page_num in page_range:
                if 1 <= page_num <= total_pages:
                    writer.add_page(reader.pages[page_num - 1])
            if len(writer.pages) == 0:
                raise ValueError("لم يتم تحديد أي صفحات صالحة")
            out_path = Path(Config.TEMP_DIR) / f"extracted_{os.urandom(4).hex()}.pdf"
            with open(out_path, "wb") as f:
                writer.write(f)
            return str(out_path)
        except Exception as e:
            raise ValueError(f"فشل استخراج الصفحات: {str(e)}")

    @staticmethod
    def split_by_page(pdf_path: str, pages_per_file: int = 1) -> List[str]:
        """تقسيم PDF إلى عدة ملفات"""
        try:
            reader = PdfReader(pdf_path)
            total_pages = len(reader.pages)
            if total_pages == 0:
                raise ValueError("الملف فارغ")
            if pages_per_file <= 0:
                raise ValueError("عدد الصفحات يجب أن يكون أكبر من 0")
            output_paths = []
            for start in range(0, total_pages, pages_per_file):
                writer = PdfWriter()
                end = min(start + pages_per_file, total_pages)
                for i in range(start, end):
                    writer.add_page(reader.pages[i])
                out_path = Path(Config.TEMP_DIR) / f"split_{start+1}_{end}_{os.urandom(4).hex()}.pdf"
                with open(out_path, "wb") as f:
                    writer.write(f)
                output_paths.append(str(out_path))
            return output_paths
        except Exception as e:
            raise ValueError(f"فشل تقسيم الملف: {str(e)}")

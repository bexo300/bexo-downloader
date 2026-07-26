import os
import io
import zipfile
from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import FreeText
import fitz
from config import Config
from utils import logger, format_size

class PDFEngine:
    @staticmethod
    def safe_metadata(reader: PdfReader) -> dict:
        meta = reader.metadata
        return {
            "pages": len(reader.pages),
            "title": getattr(meta, "title", "غير محدد") or "غير محدد",
            "author": getattr(meta, "author", "غير محدد") or "غير محدد",
            "encrypted": reader.is_encrypted,
            "size": ""
        }

    @staticmethod
    def add_page_numbers(path: str) -> str:
        reader = PdfReader(path)
        writer = PdfWriter()
        for num, page in enumerate(reader.pages, 1):
            writer.add_page(page)
            ann = FreeText(text=str(num), rect=(240,5,270,25), font_size="14pt", font_color="000000", border_color=None)
            ann.flags = 4
            writer.add_annotation(len(writer.pages)-1, ann)
        out = os.path.join(Config.TEMP_DIR, f"num_{os.urandom(4).hex()}.pdf")
        with open(out, "wb") as f: writer.write(f)
        return out

    @staticmethod
    def add_watermark(path: str, text: str) -> str:
        reader = PdfReader(path)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
            ann = FreeText(text=text, rect=(150,380,350,420), font_size="30pt", font_color="000000", border_color=None)
            ann.flags = 4
            writer.add_annotation(len(writer.pages)-1, ann)
        out = os.path.join(Config.TEMP_DIR, f"wm_{os.urandom(4).hex()}.pdf")
        with open(out, "wb") as f: writer.write(f)
        return out

    @staticmethod
    def encrypt(path: str, pw: str) -> str:
        reader = PdfReader(path)
        writer = PdfWriter()
        for p in reader.pages: writer.add_page(p)
        writer.encrypt(pw, pw)
        out = os.path.join(Config.TEMP_DIR, f"enc_{os.urandom(4).hex()}.pdf")
        with open(out, "wb") as f: writer.write(f)
        return out

    @staticmethod
    def compress(path: str) -> tuple[str, int, int]:
        before = os.path.getsize(path)
        reader = PdfReader(path)
        writer = PdfWriter()
        for p in reader.pages:
            p.compress_content_streams(level=9)
            writer.add_page(p)
        out = os.path.join(Config.TEMP_DIR, f"comp_{os.urandom(4).hex()}.pdf")
        with open(out, "wb") as f: writer.write(f)
        after = os.path.getsize(out)
        return out, before, after

    @staticmethod
    def merge(paths: list[str]) -> str:
        writer = PdfWriter()
        for p in paths: writer.append(p)
        out = os.path.join(Config.TEMP_DIR, f"merge_{os.urandom(4).hex()}.pdf")
        with open(out, "wb") as f: writer.write(f)
        return out

    @staticmethod
    def images_to_pdf(paths: list[str]) -> str:
        imgs = [Image.open(p).convert("RGB") for p in paths]
        out = os.path.join(Config.TEMP_DIR, f"imgpdf_{os.urandom(4).hex()}.pdf")
        imgs[0].save(out, save_all=True, append_images=imgs[1:])
        return out

    @staticmethod
    def pdf_to_images(path: str) -> tuple[bytes, str]:
        doc = fitz.open(path)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, pg in enumerate(doc):
                pix = pg.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("jpeg")
                zf.writestr(f"صفحة_{i+1}.jpg", img_bytes)
        doc.close()
        return buf.getvalue(), "صور_مستخرجة.zip"

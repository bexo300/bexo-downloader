import os
import re
import time
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from config import Config

logger = logging.getLogger("pdf_bot")
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler = RotatingFileHandler("bot.log", maxBytes=10*1024*1024, backupCount=3, encoding="utf-8")
handler.setFormatter(formatter)
logger.addHandler(handler)

active_users = set()

def is_user_busy(user_id: int) -> bool:
    return user_id in active_users

def set_user_busy(user_id: int, busy: bool = True):
    if busy:
        active_users.add(user_id)
    else:
        active_users.discard(user_id)

def clean_old_files():
    now = time.time()
    temp_path = Path(Config.TEMP_DIR)
    if not temp_path.exists():
        return
    for file_path in temp_path.iterdir():
        if file_path.is_file():
            try:
                if now - file_path.stat().st_mtime > Config.MAX_FILE_AGE:
                    file_path.unlink()
            except Exception:
                pass

def validate_page_range(range_str: str, total: int) -> list:
    if not range_str:
        raise ValueError("أدخل نطاق الصفحات")
    pages = set()
    range_str = range_str.replace(" ", "")
    if not range_str:
        raise ValueError("النطاق فارغ")
    for part in range_str.split(","):
        if not part:
            continue
        if "-" in part:
            try:
                s, e = map(int, part.split("-"))
                if not (1 <= s <= e <= total):
                    raise ValueError(f"نطاق {s}-{e} غير صالح")
                pages.update(range(s, e + 1))
            except ValueError:
                raise ValueError(f"تنسيق غير صحيح: {part}")
        else:
            try:
                p = int(part)
                if not (1 <= p <= total):
                    raise ValueError(f"الصفحة {p} غير موجودة")
                pages.add(p)
            except ValueError:
                raise ValueError(f"قيمة غير صالحة: {part}")
    if not pages:
        raise ValueError("لم يتم تحديد أي صفحات صالحة")
    return sorted(pages)

def format_size(size: int) -> str:
    if size < 1024:
        return f"{size} ب"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} كيلوبايت"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} ميجابايت"
    else:
        return f"{size / (1024 * 1024 * 1024):.2f} جيجابايت"

def sanitize_filename(filename: str) -> str:
    if not filename:
        return "ملف"
    filename = re.sub(r'[\\/*?:"<>|]', "", filename)
    filename = re.sub(r'\s+', " ", filename).strip()
    return filename or "ملف"

def safe_remove(file_path: str) -> bool:
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
    except Exception:
        pass
    return False

def ensure_extension(filename: str) -> str:
    """إضافة امتداد .pdf إذا كان مفقوداً"""
    if not filename:
        return "ملف.pdf"
    filename = sanitize_filename(filename)
    known_extensions = ['.pdf', '.zip', '.jpg', '.jpeg', '.png']
    if any(filename.lower().endswith(ext) for ext in known_extensions):
        return filename
    return filename + ".pdf"

import os
import re
import time
import shutil
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from config import Config

logger = logging.getLogger("pdf_bot")
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler = RotatingFileHandler("bot.log", maxBytes=10*1024*1024, backupCount=3, encoding="utf-8")
handler.setFormatter(formatter)
logger.addHandler(handler)

# منع التكرار والسبام
active_users = set()

def is_user_busy(user_id: int) -> bool:
    return user_id in active_users

def set_user_busy(user_id: int, busy: bool = True):
    if busy: active_users.add(user_id)
    else: active_users.discard(user_id)

# تنظيف الملفات القديمة
def clean_old_files():
    now = time.time()
    for root, _, files in os.walk(Config.TEMP_DIR):
        for f in files:
            path = os.path.join(root, f)
            if now - os.path.getmtime(path) > Config.MAX_FILE_AGE:
                try: os.remove(path)
                except: pass

# التحقق من النطاقات والأرقام
def validate_page_range(range_str: str, total: int):
    if not range_str: raise ValueError("أدخل نطاق الصفحات")
    pages = set()
    for part in range_str.replace(" ", "").split(","):
        if "-" in part:
            s, e = map(int, part.split("-"))
            if not (1 <= s <= e <= total): raise ValueError("نطاق غير صالح")
            pages.update(range(s, e+1))
        else:
            p = int(part)
            if not (1 <= p <= total): raise ValueError(f"صفحة {p} غير موجودة")
            pages.add(p)
    return sorted(pages)

# تنسيق الحجم
def format_size(size: int) -> str:
    for u in ['ب', 'كيلوبايت', 'ميجابايت']:
        if size < 1024: return f"{size:.1f} {u}"
        size /= 1024
    return f"{size:.1f} جيجابايت"

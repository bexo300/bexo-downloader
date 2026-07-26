import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    CHANNEL_USERNAME = "bexo50"
    MAX_FILE_SIZE = 50 * 1024 * 1024
    TEMP_DIR = os.path.join(os.path.dirname(__file__), "temp")
    MAX_SESSION_TIME = 600  # 10 دقائق لإنهاء الجلسة تلقائياً
    MAX_OPERATIONS_PER_USER = 1
    COMPRESS_QUALITY = 85
    CLEANUP_INTERVAL = 1800  # كل 30 دقيقة تنظيف الملفات القديمة
    MAX_FILE_AGE = 3600  # حذف الملفات الأقدم من ساعة

    @classmethod
    def ensure_dirs(cls):
        os.makedirs(cls.TEMP_DIR, exist_ok=True)

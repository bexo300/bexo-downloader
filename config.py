import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    # ✅ قائمة المشرفين (معرفات المستخدمين)
    ADMINS = list(map(int, os.getenv("ADMINS", "").split(","))) if os.getenv("ADMINS") else []
    
    MAX_FILE_SIZE = 50 * 1024 * 1024
    TEMP_DIR = os.path.join(os.path.dirname(__file__), "temp")
    MAX_SESSION_TIME = 600
    MAX_OPERATIONS_PER_USER = 1
    COMPRESS_QUALITY = 85
    CLEANUP_INTERVAL = 1800
    MAX_FILE_AGE = 3600
    MAX_FILES_PER_SESSION = 20
    SUPPORTED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp", "image/bmp", "image/tiff"]
    SUPPORTED_DOC_TYPES = ["application/pdf"]
    ALLOWED_TYPES = SUPPORTED_IMAGE_TYPES + SUPPORTED_DOC_TYPES
    FORCED_CHANNELS = []

    @classmethod
    def ensure_dirs(cls):
        os.makedirs(cls.TEMP_DIR, exist_ok=True)

# keyboards.py
from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton

MAIN_MENU = ReplyKeyboardMarkup([
    ["📎 دمج PDF", "🖼️ صور لـ PDF"],
    ["📸 استخراج صور", "🔢 ترقيم الصفحات"],
    ["✂️ تقسيم", "🗑️ حذف صفحات"],
    ["📉 ضغط", "💧 علامة مائية"],
    ["🔒 حماية", "🔓 إزالة الحماية"],
    ["ℹ️ معلومات", "🧹 مسح الملفات"]
], resize_keyboard=True)

ACTION_MENU = ReplyKeyboardMarkup([
    ["✅ إنهاء العملية", "➕ إضافة ملفات أخرى"],
    ["❌ إلغاء"]
], resize_keyboard=True)

BACK_BTN = InlineKeyboardMarkup([
    [InlineKeyboardButton("⬅️ رجوع", callback_data="back")]
])

CANCEL_BTN = InlineKeyboardMarkup([
    [InlineKeyboardButton("❌ إلغاء", callback_data="cancel")]
])

# أزرار إضافية للعمليات المتقدمة
PAGE_NUMBER_MENU = ReplyKeyboardMarkup([
    ["📄 كل الصفحات", "📝 نطاق مخصص"],
    ["❌ إلغاء"]
], resize_keyboard=True)

COMPRESS_QUALITY_MENU = ReplyKeyboardMarkup([
    ["📊 ضغط عالي", "📈 ضغط متوسط"],
    ["📉 ضغط منخفض", "❌ إلغاء"]
], resize_keyboard=True)

"""
Bexo Downloader - Inline Keyboards
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.locales import get_text


def quality_keyboard(qualities: list, lang: str = "ar") -> InlineKeyboardMarkup:
    """Create quality selection keyboard.
    
    Args:
        qualities: List of available qualities
        lang: User language
        
    Returns:
        Inline keyboard markup
    """
    buttons = []
    
    for quality in qualities:
        quality_key = f"quality_{quality}"
        quality_text = get_text(quality_key, lang, default=f"📺 {quality}")
        buttons.append([
            InlineKeyboardButton(quality_text, callback_data=f"dl:video:{quality}")
        ])
    
    buttons.append([
        InlineKeyboardButton(get_text("download_audio", lang), callback_data="dl:audio")
    ])
    buttons.append([
        InlineKeyboardButton(get_text("cancel", lang), callback_data="cancel")
    ])
    
    return InlineKeyboardMarkup(buttons)


def format_keyboard(lang: str = "ar") -> InlineKeyboardMarkup:
    """Create format selection keyboard.
    
    Args:
        lang: User language
        
    Returns:
        Inline keyboard markup
    """
    buttons = [
        [
            InlineKeyboardButton(get_text("download_video", lang), callback_data="format:video"),
            InlineKeyboardButton(get_text("download_audio", lang), callback_data="format:audio"),
        ],
        [
            InlineKeyboardButton(get_text("cancel", lang), callback_data="cancel")
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def admin_keyboard(lang: str = "ar") -> InlineKeyboardMarkup:
    """Create admin panel keyboard.
    
    Args:
        lang: User language
        
    Returns:
        Inline keyboard markup
    """
    buttons = [
        [
            InlineKeyboardButton("📊 Statistics", callback_data="admin:stats"),
            InlineKeyboardButton("👥 Users", callback_data="admin:users"),
        ],
        [
            InlineKeyboardButton("📢 Broadcast", callback_data="admin:broadcast"),
            InlineKeyboardButton("🚫 Ban User", callback_data="admin:ban"),
        ],
        [
            InlineKeyboardButton("✅ Unban User", callback_data="admin:unban"),
            InlineKeyboardButton("💾 Backup", callback_data="admin:backup"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def cancel_keyboard(lang: str = "ar") -> InlineKeyboardMarkup:
    """Create cancel button keyboard.
    
    Args:
        lang: User language
        
    Returns:
        Inline keyboard markup
    """
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(get_text("cancel", lang), callback_data="cancel")]
    ])

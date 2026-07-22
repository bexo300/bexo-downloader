"""Localization package for Bexo Downloader."""

from .ar import ARABIC
from .en import ENGLISH

TRANSLATIONS = {
    "ar": ARABIC,
    "en": ENGLISH,
}

def get_text(key: str, lang: str = "ar", **kwargs) -> str:
    """Get translated text.
    
    Args:
        key: Translation key
        lang: Language code
        **kwargs: Format arguments
        
    Returns:
        Translated and formatted text
    """
    translation = TRANSLATIONS.get(lang, ARABIC)
    text = translation.get(key, key)
    
    if kwargs:
        try:
            return text.format(**kwargs)
        except KeyError:
            return text
    
    return text

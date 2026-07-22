
# File 11: bot/utils/helpers.py
helpers_py = '''"""
Bexo Downloader - Utility Helpers
Common utility functions used across the bot
"""

import hashlib
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

import humanize


def generate_progress_bar(percentage: float, length: int = 20) -> str:
    """Generate a text-based progress bar.
    
    Args:
        percentage: Progress percentage (0-100)
        length: Length of the progress bar
        
    Returns:
        String representation of the progress bar
    """
    filled = int(length * percentage / 100)
    empty = length - filled
    bar = "█" * filled + "░" * empty
    return f"[{bar}] {percentage:.1f}%"


def format_size(size_bytes: int) -> str:
    """Format bytes to human-readable string.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Human-readable size string
    """
    return humanize.naturalsize(size_bytes, binary=True)


def format_duration(seconds: float) -> str:
    """Format seconds to human-readable duration.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Human-readable duration string
    """
    return humanize.precisedelta(timedelta(seconds=int(seconds)))


def sanitize_filename(filename: str, max_length: int = 200) -> str:
    """Sanitize filename for safe filesystem usage.
    
    Args:
        filename: Original filename
        max_length: Maximum filename length
        
    Returns:
        Sanitized filename
    """
    # Remove invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove control characters
    sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', sanitized)
    # Trim whitespace
    sanitized = sanitized.strip()
    # Limit length
    if len(sanitized) > max_length:
        name, ext = Path(sanitized).stem, Path(sanitized).suffix
        sanitized = name[:max_length - len(ext) - 3] + "..." + ext
    return sanitized or "unknown"


def extract_platform(url: str) -> Optional[str]:
    """Extract platform name from URL.
    
    Args:
        url: Media URL
        
    Returns:
        Platform name or None
    """
    patterns = {
        "tiktok": r"tiktok\\.com",
        "instagram": r"instagram\\.com",
        "facebook": r"facebook\\.com|fb\\.watch",
        "youtube": r"youtube\\.com|youtu\\.be",
        "twitter": r"twitter\\.com|x\\.com",
        "threads": r"threads\\.net",
        "pinterest": r"pinterest\\.",
        "snapchat": r"snapchat\\.com",
        "reddit": r"reddit\\.com|redd\\.it",
        "vimeo": r"vimeo\\.com",
        "dailymotion": r"dailymotion\\.com",
        "soundcloud": r"soundcloud\\.com",
        "likee": r"likee\\.video|likee\\.com",
    }
    
    url_lower = url.lower()
    for platform, pattern in patterns.items():
        if re.search(pattern, url_lower):
            return platform
    return None


def is_valid_url(url: str) -> bool:
    """Check if string is a valid URL.
    
    Args:
        url: URL string to validate
        
    Returns:
        True if valid URL
    """
    pattern = re.compile(
        r'^(https?://)?'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\\.)+[A-Z]{2,6}\\.?|'
        r'localhost|'
        r'\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3})'
        r'(?::\\d+)?'
        r'(?:/?|[/?]\\S+)$',
        re.IGNORECASE
    )
    return bool(pattern.match(url))


def generate_file_hash(content: bytes) -> str:
    """Generate SHA-256 hash of file content.
    
    Args:
        content: File bytes
        
    Returns:
        Hex digest of hash
    """
    return hashlib.sha256(content).hexdigest()[:16]


def get_platform_icon(platform: str) -> str:
    """Get emoji icon for platform.
    
    Args:
        platform: Platform name
        
    Returns:
        Emoji icon string
    """
    icons = {
        "tiktok": "🎵",
        "instagram": "📸",
        "facebook": "📘",
        "youtube": "▶️",
        "twitter": "🐦",
        "threads": "🧵",
        "pinterest": "📌",
        "snapchat": "👻",
        "reddit": "🔴",
        "vimeo": "🎬",
        "dailymotion": "📺",
        "soundcloud": "☁️",
        "likee": "⭐",
    }
    return icons.get(platform, "🔗")


def format_number(num: int) -> str:
    """Format large numbers with commas.
    
    Args:
        num: Number to format
        
    Returns:
        Formatted number string
    """
    return humanize.intcomma(num)


def calculate_eta(downloaded: int, total: int, speed: float) -> str:
    """Calculate estimated time of arrival for download.
    
    Args:
        downloaded: Bytes downloaded
        total: Total bytes
        speed: Download speed in bytes/sec
        
    Returns:
        ETA string
    """
    if speed <= 0:
        return "∞"
    remaining = total - downloaded
    seconds = remaining / speed
    return format_duration(seconds)
'''

with open("/mnt/agents/output/bexo_downloader/bot/utils/helpers.py", "w", encoding="utf-8") as f:
    f.write(helpers_py)

print("✅ bot/utils/helpers.py created")


# File 12: bot/utils/security.py
security_py = '''"""
Bexo Downloader - Security Utilities
Protection against common attacks and malicious content
"""

import hashlib
import os
import re
from pathlib import Path
from typing import Optional, Set

import magic


class SecurityManager:
    """Manages security checks and validations."""
    
    # Allowed MIME types for downloads
    ALLOWED_MIME_TYPES: Set[str] = {
        "video/mp4",
        "video/webm",
        "video/x-matroska",
        "video/avi",
        "video/quicktime",
        "audio/mpeg",
        "audio/mp3",
        "audio/wav",
        "audio/ogg",
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
    }
    
    # Blocked file extensions
    BLOCKED_EXTENSIONS: Set[str] = {
        ".exe", ".dll", ".bat", ".cmd", ".sh", ".php",
        ".py", ".js", ".jar", ".apk", ".ipa", ".deb",
        ".rpm", ".msi", ".app", ".dmg", ".iso", ".img",
        ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2",
    }
    
    # Suspicious URL patterns
    SUSPICIOUS_PATTERNS = [
        r"(\\.\\./|\\.\\.\\\\)",  # Path traversal
        r"[<>'\";|&`$]",  # Special characters
        r"(javascript|data):",  # Protocol attacks
        r"\\x00",  # Null bytes
    ]
    
    def __init__(self, max_file_size_mb: int = 2048) -> None:
        """Initialize security manager.
        
        Args:
            max_file_size_mb: Maximum allowed file size in MB
        """
        self.max_file_size = max_file_size_mb * 1024 * 1024
    
    def validate_url(self, url: str) -> tuple[bool, Optional[str]]:
        """Validate URL for security issues.
        
        Args:
            url: URL to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not url or len(url) > 2048:
            return False, "Invalid URL length"
        
        for pattern in self.SUSPICIOUS_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                return False, "Suspicious URL pattern detected"
        
        return True, None
    
    def validate_file_path(self, file_path: Path) -> tuple[bool, Optional[str]]:
        """Validate file path for security issues.
        
        Args:
            file_path: Path to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Resolve to absolute path
            resolved = file_path.resolve()
            
            # Check for path traversal
            download_root = Path("bot/downloads").resolve()
            if not str(resolved).startswith(str(download_root)):
                return False, "Path traversal detected"
            
            # Check extension
            if file_path.suffix.lower() in self.BLOCKED_EXTENSIONS:
                return False, "Blocked file extension"
            
            return True, None
        except Exception:
            return False, "Invalid file path"
    
    def validate_file_content(self, file_path: Path) -> tuple[bool, Optional[str]]:
        """Validate file content for security issues.
        
        Args:
            file_path: Path to file
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check file size
            file_size = file_path.stat().st_size
            if file_size > self.max_file_size:
                return False, f"File too large: {file_size} bytes"
            
            # Check MIME type
            mime = magic.from_file(str(file_path), mime=True)
            if mime not in self.ALLOWED_MIME_TYPES:
                return False, f"Invalid file type: {mime}"
            
            return True, None
        except Exception as e:
            return False, f"File validation error: {str(e)}"
    
    def sanitize_input(self, text: str, max_length: int = 1000) -> str:
        """Sanitize user input.
        
        Args:
            text: Input text
            max_length: Maximum allowed length
            
        Returns:
            Sanitized text
        """
        # Remove null bytes
        text = text.replace("\\x00", "")
        # Remove control characters
        text = re.sub(r"[\\x00-\\x1f\\x7f-\\x9f]", "", text)
        # Limit length
        return text[:max_length]
    
    def generate_safe_filename(self, original_name: str) -> str:
        """Generate safe filename from original.
        
        Args:
            original_name: Original filename
            
        Returns:
            Safe filename
        """
        # Remove path components
        name = os.path.basename(original_name)
        # Remove dangerous characters
        name = re.sub(r"[<>:\\"/\\\\|?*]", "_", name)
        # Remove control characters
        name = re.sub(r"[\\x00-\\x1f\\x7f-\\x9f]", "", name)
        # Limit length
        if len(name) > 200:
            stem, ext = Path(name).stem, Path(name).suffix
            name = stem[:197] + "..." + ext
        return name or "unknown_file"
    
    def hash_user_id(self, user_id: int) -> str:
        """Hash user ID for logging without exposing real ID.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Hashed ID string
        """
        return hashlib.sha256(str(user_id).encode()).hexdigest()[:12]
'''

with open("/mnt/agents/output/bexo_downloader/bot/utils/security.py", "w", encoding="utf-8") as f:
    f.write(security_py)

print("✅ bot/utils/security.py created")

"""
Bexo Downloader - Admin Filter
"""

from telegram import Update
from telegram.ext import filters


class AdminFilter(filters.BaseFilter):
    """Filter for admin users."""
    
    def __init__(self, admin_ids: list[int]):
        self.admin_ids = admin_ids
    
    def check_update(self, update: Update) -> bool:
        """Check if user is admin.
        
        Args:
            update: Telegram update
            
        Returns:
            True if user is admin
        """
        if not update.effective_user:
            return False
        return update.effective_user.id in self.admin_ids

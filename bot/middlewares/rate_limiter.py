"""
Bexo Downloader - Rate Limiter Middleware
Prevents spam and flooding
"""

import asyncio
import logging
import time
from collections import defaultdict
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes


logger = logging.getLogger("bexo.rate_limiter")


class RateLimiter:
    """Rate limiter for user requests."""
    
    def __init__(
        self,
        requests_per_minute: int = 10,
        block_duration: int = 300
    ) -> None:
        """Initialize rate limiter.
        
        Args:
            requests_per_minute: Max requests per minute
            block_duration: Block duration in seconds
        """
        self.requests_per_minute = requests_per_minute
        self.block_duration = block_duration
        self.user_requests: dict[int, list[float]] = defaultdict(list)
        self.blocked_users: dict[int, float] = {}
    
    def is_blocked(self, user_id: int) -> bool:
        """Check if user is currently blocked.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if blocked
        """
        if user_id in self.blocked_users:
            if time.time() - self.blocked_users[user_id] < self.block_duration:
                return True
            del self.blocked_users[user_id]
        return False
    
    def can_proceed(self, user_id: int) -> bool:
        """Check if user can make a request.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if request is allowed
        """
        if self.is_blocked(user_id):
            return False
        
        now = time.time()
        minute_ago = now - 60
        
        # Clean old requests
        self.user_requests[user_id] = [
            req_time for req_time in self.user_requests[user_id]
            if req_time > minute_ago
        ]
        
        # Check limit
        if len(self.user_requests[user_id]) >= self.requests_per_minute:
            self.blocked_users[user_id] = now
            logger.warning(f"User {user_id} rate limited")
            return False
        
        self.user_requests[user_id].append(now)
        return True
    
    async def middleware(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
        """Rate limiting middleware.
        
        Args:
            update: Telegram update
            context: Bot context
            
        Returns:
            True if should proceed
        """
        if not update.effective_user:
            return True
        
        user_id = update.effective_user.id
        
        if not self.can_proceed(user_id):
            await update.message.reply_text(
                "⏳ Too many requests. Please wait a few minutes."
            ) if update.message else None
            return False
        
        return True

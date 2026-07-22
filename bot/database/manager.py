"""
Bexo Downloader - Database Manager
Async database operations with SQLAlchemy
"""

import logging
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from bot.database.base import Base
from bot.models.download import Download
from bot.models.user import User


logger = logging.getLogger("bexo.database")


class DatabaseManager:
    """Manages all database operations."""
    
    def __init__(self, database_url: str) -> None:
        """Initialize database manager.
        
        Args:
            database_url: Database connection URL
        """
        # Convert SQLite URL to async
        if database_url.startswith("sqlite:///"):
            database_url = database_url.replace("sqlite:///", "sqlite+aiosqlite:///")
        
        self.engine = create_async_engine(
            database_url,
            echo=False,
            future=True
        )
        self.async_session = sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    
    async def init(self) -> None:
        """Initialize database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created")
    
    async def get_user(self, telegram_id: int) -> Optional[User]:
        """Get user by Telegram ID.
        
        Args:
            telegram_id: Telegram user ID
            
        Returns:
            User object or None
        """
        async with self.async_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            return result.scalar_one_or_none()
    
    async def create_user(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        language: str = "ar"
    ) -> User:
        """Create new user.
        
        Args:
            telegram_id: Telegram user ID
            username: Telegram username
            first_name: First name
            last_name: Last name
            language: Preferred language
            
        Returns:
            Created user
        """
        async with self.async_session() as session:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                language=language
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            logger.info(f"Created user: {telegram_id}")
            return user
    
    async def update_user_activity(self, telegram_id: int) -> None:
        """Update user's last activity timestamp.
        
        Args:
            telegram_id: Telegram user ID
        """
        async with self.async_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            if user:
                from datetime import datetime
                user.last_activity = datetime.utcnow()
                await session.commit()
    
    async def increment_downloads(
        self,
        telegram_id: int,
        media_type: str
    ) -> None:
        """Increment user's download counter.
        
        Args:
            telegram_id: Telegram user ID
            media_type: Type of media downloaded
        """
        async with self.async_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            if user:
                user.total_downloads += 1
                if media_type == "video":
                    user.video_downloads += 1
                elif media_type == "audio":
                    user.audio_downloads += 1
                elif media_type == "image":
                    user.image_downloads += 1
                await session.commit()
    
    async def record_download(self, download: Download) -> None:
        """Record a download in history.
        
        Args:
            download: Download object to record
        """
        async with self.async_session() as session:
            session.add(download)
            await session.commit()
    
    async def get_stats(self) -> dict:
        """Get bot statistics.
        
        Returns:
            Dictionary with statistics
        """
        async with self.async_session() as session:
            total_users = await session.scalar(select(func.count(User.id)))
            total_downloads = await session.scalar(
                select(func.count(Download.id))
            )
            video_downloads = await session.scalar(
                select(func.count(Download.id)).where(
                    Download.media_type == "video"
                )
            )
            audio_downloads = await session.scalar(
                select(func.count(Download.id)).where(
                    Download.media_type == "audio"
                )
            )
            image_downloads = await session.scalar(
                select(func.count(Download.id)).where(
                    Download.media_type == "image"
                )
            )
            
            return {
                "total_users": total_users or 0,
                "total_downloads": total_downloads or 0,
                "video_downloads": video_downloads or 0,
                "audio_downloads": audio_downloads or 0,
                "image_downloads": image_downloads or 0,
            }
    
    async def get_top_users(self, limit: int = 10) -> List[User]:
        """Get top users by download count.
        
        Args:
            limit: Number of users to return
            
        Returns:
            List of top users
        """
        async with self.async_session() as session:
            result = await session.execute(
                select(User)
                .order_by(User.total_downloads.desc())
                .limit(limit)
            )
            return result.scalars().all()
    
    async def ban_user(self, telegram_id: int) -> bool:
        """Ban a user.
        
        Args:
            telegram_id: Telegram user ID
            
        Returns:
            True if user was found and banned
        """
        async with self.async_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            if user:
                user.is_banned = True
                await session.commit()
                logger.info(f"Banned user: {telegram_id}")
                return True
            return False
    
    async def unban_user(self, telegram_id: int) -> bool:
        """Unban a user.
        
        Args:
            telegram_id: Telegram user ID
            
        Returns:
            True if user was found and unbanned
        """
        async with self.async_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            if user:
                user.is_banned = False
                await session.commit()
                logger.info(f"Unbanned user: {telegram_id}")
                return True
            return False
    
    async def get_all_users(self) -> List[User]:
        """Get all users for broadcasting.
        
        Returns:
            List of all users
        """
        async with self.async_session() as session:
            result = await session.execute(select(User))
            return result.scalars().all()

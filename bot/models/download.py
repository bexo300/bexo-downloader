"""
Bexo Downloader - Download Model
SQLAlchemy model for download history
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from bot.database.base import Base


class Download(Base):
    """Download model for tracking all downloads."""
    
    __tablename__ = "downloads"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    platform: Mapped[str] = mapped_column(String(50))
    url: Mapped[str] = mapped_column(String(2000))
    media_type: Mapped[str] = mapped_column(String(20))  # video, audio, image
    quality: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, success, failed
    error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<Download(id={self.id}, platform={self.platform}, status={self.status})>"

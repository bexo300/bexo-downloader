"""
Bexo Downloader - Downloader Service
Handles all media downloads using yt-dlp with async support
"""

import asyncio
import logging
import os
import shutil
from pathlib import Path
from typing import Callable, Optional

import yt_dlp


logger = logging.getLogger("bexo.downloader")


class DownloadProgress:
    """Tracks download progress."""
    
    def __init__(self) -> None:
        self.downloaded: float = 0.0
        self.total: float = 0.0
        self.speed: float = 0.0
        self.eta: float = 0.0
        self.status: str = "pending"
        self.percentage: float = 0.0
    
    def update(self, d: dict) -> None:
        """Update progress from yt-dlp hook.
        
        Args:
            d: Progress dictionary from yt-dlp
        """
        if d["status"] == "downloading":
            self.status = "downloading"
            self.downloaded = d.get("downloaded_bytes", 0)
            self.total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            self.speed = d.get("speed", 0)
            self.eta = d.get("eta", 0)
            if self.total > 0:
                self.percentage = (self.downloaded / self.total) * 100
        elif d["status"] == "finished":
            self.status = "finished"
            self.percentage = 100.0


class DownloaderService:
    """Service for downloading media from various platforms."""
    
    # Supported platforms configuration
    SUPPORTED_PLATFORMS = {
        "tiktok": {"name": "TikTok", "supports_video": True, "supports_audio": True},
        "instagram": {"name": "Instagram", "supports_video": True, "supports_audio": False, "supports_images": True},
        "facebook": {"name": "Facebook", "supports_video": True, "supports_audio": True},
        "youtube": {"name": "YouTube", "supports_video": True, "supports_audio": True},
        "twitter": {"name": "X (Twitter)", "supports_video": True, "supports_audio": False, "supports_images": True},
        "threads": {"name": "Threads", "supports_video": True, "supports_audio": False, "supports_images": True},
        "pinterest": {"name": "Pinterest", "supports_video": True, "supports_audio": False, "supports_images": True},
        "snapchat": {"name": "Snapchat", "supports_video": True, "supports_audio": False},
        "reddit": {"name": "Reddit", "supports_video": True, "supports_audio": True, "supports_images": True},
        "vimeo": {"name": "Vimeo", "supports_video": True, "supports_audio": True},
        "dailymotion": {"name": "Dailymotion", "supports_video": True, "supports_audio": True},
        "soundcloud": {"name": "SoundCloud", "supports_video": False, "supports_audio": True},
        "likee": {"name": "Likee", "supports_video": True, "supports_audio": True},
    }
    
    def __init__(
        self,
        max_concurrent: int = 5,
        download_path: str = "bot/downloads",
        max_file_size: int = 2048,
        ffmpeg_path: Optional[str] = None
    ) -> None:
        """Initialize downloader service.
        
        Args:
            max_concurrent: Maximum concurrent downloads
            download_path: Path to save downloads
            max_file_size: Maximum file size in MB
            ffmpeg_path: Path to FFmpeg binary
        """
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.download_path = Path(download_path)
        self.download_path.mkdir(parents=True, exist_ok=True)
        self.max_file_size = max_file_size * 1024 * 1024  # Convert to bytes
        self.ffmpeg_path = ffmpeg_path or shutil.which("ffmpeg")
        self.active_downloads: dict[str, DownloadProgress] = {}
        
        logger.info(
            f"Downloader initialized: max_concurrent={max_concurrent}, "
            f"max_file_size={max_file_size}MB"
        )
    
    def _get_ydl_opts(
        self,
        output_path: Path,
        quality: Optional[str] = None,
        audio_only: bool = False,
        progress_hook: Optional[Callable] = None
    ) -> dict:
        """Get yt-dlp options.
        
        Args:
            output_path: Output file path
            quality: Video quality preference
            audio_only: Download audio only
            progress_hook: Progress callback
            
        Returns:
            yt-dlp options dictionary
        """
        opts = {
            "outtmpl": str(output_path / "%(title)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
        }
        
        if self.ffmpeg_path:
            opts["ffmpeg_location"] = self.ffmpeg_path
        
        if progress_hook:
            opts["progress_hooks"] = [progress_hook]
        
        if audio_only:
            opts.update({
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
            })
        else:
            if quality:
                height = int(quality.replace("p", ""))
                opts["format"] = f"bestvideo[height<={height}]+bestaudio/best[height<={height}]/best"
            else:
                opts["format"] = "bestvideo+bestaudio/best"
            
            opts["merge_output_format"] = "mp4"
        
        opts["max_filesize"] = self.max_file_size
        
        return opts
    
    async def get_media_info(self, url: str) -> Optional[dict]:
        """Get media information without downloading.
        
        Args:
            url: Media URL
            
        Returns:
            Media information dictionary or None
        """
        try:
            loop = asyncio.get_event_loop()
            
            def _extract_info():
                with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
                    return ydl.extract_info(url, download=False)
            
            info = await loop.run_in_executor(None, _extract_info)
            
            if not info:
                return None
            
            # Extract relevant information
            formats = []
            if "formats" in info:
                seen_heights = set()
                for f in info["formats"]:
                    if f.get("vcodec") != "none" and f.get("height"):
                        height = f["height"]
                        if height not in seen_heights:
                            seen_heights.add(height)
                            formats.append({
                                "format_id": f["format_id"],
                                "height": height,
                                "ext": f.get("ext", "mp4"),
                            })
            
            formats.sort(key=lambda x: x["height"])
            
            return {
                "title": info.get("title", "Unknown"),
                "duration": info.get("duration"),
                "uploader": info.get("uploader"),
                "view_count": info.get("view_count"),
                "like_count": info.get("like_count"),
                "thumbnail": info.get("thumbnail"),
                "description": info.get("description", "")[:200],
                "formats": formats,
                "is_live": info.get("is_live", False),
            }
            
        except Exception as e:
            logger.error(f"Error extracting info: {e}")
            return None
    
    async def download(
        self,
        url: str,
        download_id: str,
        quality: Optional[str] = None,
        audio_only: bool = False,
        progress_callback: Optional[Callable] = None
    ) -> Optional[Path]:
        """Download media from URL.
        
        Args:
            url: Media URL
            download_id: Unique download identifier
            quality: Video quality preference
            audio_only: Download audio only
            progress_callback: Progress callback function
            
        Returns:
            Path to downloaded file or None
        """
        async with self.semaphore:
            progress = DownloadProgress()
            self.active_downloads[download_id] = progress
            
            try:
                output_path = self.download_path / download_id
                output_path.mkdir(exist_ok=True)
                
                def _progress_hook(d: dict) -> None:
                    progress.update(d)
                    if progress_callback:
                        asyncio.create_task(progress_callback(progress))
                
                loop = asyncio.get_event_loop()
                
                def _download():
                    opts = self._get_ydl_opts(
                        output_path, quality, audio_only, _progress_hook
                    )
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        return ydl.download([url])
                
                await loop.run_in_executor(None, _download)
                
                # Find downloaded file
                files = list(output_path.iterdir())
                if files:
                    downloaded_file = files[0]
                    
                    # Check file size
                    if downloaded_file.stat().st_size > self.max_file_size:
                        downloaded_file.unlink()
                        raise ValueError("File too large")
                    
                    return downloaded_file
                
                return None
                
            except Exception as e:
                logger.error(f"Download failed: {e}")
                return None
            
            finally:
                del self.active_downloads[download_id]
                # Cleanup empty directory
                if output_path.exists() and not any(output_path.iterdir()):
                    output_path.rmdir()
    
    async def cleanup_downloads(self) -> int:
        """Clean up old download files.
        
        Returns:
            Number of files deleted
        """
        deleted = 0
        current_time = asyncio.get_event_loop().time()
        
        for item in self.download_path.iterdir():
            if item.is_file():
                # Delete files older than 1 hour
                stat = item.stat()
                age = current_time - stat.st_mtime
                if age > 3600:
                    item.unlink()
                    deleted += 1
            elif item.is_dir():
                # Clean and remove empty directories
                for file in item.iterdir():
                    file.unlink()
                    deleted += 1
                item.rmdir()
        
        logger.info(f"Cleaned up {deleted} files")
        return deleted
    
    def is_platform_supported(self, platform: str) -> bool:
        """Check if platform is supported.
        
        Args:
            platform: Platform name
            
        Returns:
            True if supported
        """
        return platform.lower() in self.SUPPORTED_PLATFORMS
    
    def get_platform_info(self, platform: str) -> Optional[dict]:
        """Get platform information.
        
        Args:
            platform: Platform name
            
        Returns:
            Platform info dictionary or None
        """
        return self.SUPPORTED_PLATFORMS.get(platform.lower())

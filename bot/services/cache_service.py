"""
Bexo Downloader - Cache Service
In-memory caching for improved performance
"""

import hashlib
import logging
from typing import Any, Optional

from cachetools import TTLCache


logger = logging.getLogger("bexo.cache")


class CacheService:
    """Manages in-memory caching with TTL."""
    
    def __init__(self, maxsize: int = 1000, ttl: int = 3600) -> None:
        """Initialize cache service.
        
        Args:
            maxsize: Maximum number of cached items
            ttl: Time to live in seconds
        """
        self.cache: TTLCache = TTLCache(maxsize=maxsize, ttl=ttl)
        self.media_info_cache: TTLCache = TTLCache(maxsize=500, ttl=1800)
        logger.info(f"Cache initialized: maxsize={maxsize}, ttl={ttl}s")
    
    def _generate_key(self, *args: str) -> str:
        """Generate cache key from arguments.
        
        Args:
            *args: Key components
            
        Returns:
            Hashed key string
        """
        key_string = ":".join(str(arg) for arg in args)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None
        """
        return self.cache.get(key)
    
    def set(self, key: str, value: Any) -> None:
        """Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        self.cache[key] = value
    
    def get_media_info(self, url: str) -> Optional[dict]:
        """Get cached media info.
        
        Args:
            url: Media URL
            
        Returns:
            Cached media info or None
        """
        key = self._generate_key("media_info", url)
        return self.media_info_cache.get(key)
    
    def set_media_info(self, url: str, info: dict) -> None:
        """Cache media info.
        
        Args:
            url: Media URL
            info: Media information dictionary
        """
        key = self._generate_key("media_info", url)
        self.media_info_cache[key] = info
    
    def clear(self) -> None:
        """Clear all caches."""
        self.cache.clear()
        self.media_info_cache.clear()
        logger.info("Cache cleared")
    
    def get_stats(self) -> dict:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache stats
        """
        return {
            "main_cache_size": len(self.cache),
            "media_cache_size": len(self.media_info_cache),
            "main_cache_maxsize": self.cache.maxsize,
            "media_cache_maxsize": self.media_info_cache.maxsize,
        }

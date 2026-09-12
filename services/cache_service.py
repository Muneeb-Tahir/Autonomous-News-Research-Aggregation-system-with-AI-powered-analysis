"""
Simple in-memory TTL cache for the News Intelligence Agent.

Prevents redundant Gemini calls when multiple users (or the same user)
request the same Top 5 within a short window.
"""

import time
from typing import Any, Optional, Dict

from config.settings import CACHE_TTL_SECONDS
from utils.logger import get_logger

logger = get_logger(__name__)


class CacheService:
    """Simple in-memory cache with time-based expiration.

    Each entry has a TTL (time-to-live). After TTL expires,
    the entry is considered stale and will be regenerated.
    """

    def __init__(self, ttl: int = None):
        """Initialize cache.

        Args:
            ttl: Time-to-live in seconds. Defaults to CACHE_TTL_SECONDS.
        """
        self.ttl = ttl or CACHE_TTL_SECONDS
        self._store: Dict[str, Dict[str, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        """Get a cached value if it exists and hasn't expired.

        Args:
            key: Cache key.

        Returns:
            Cached value, or None if not found or expired.
        """
        if key not in self._store:
            return None

        entry = self._store[key]
        if time.time() - entry["timestamp"] > self.ttl:
            # Expired — remove and return None
            del self._store[key]
            logger.debug(f"Cache expired: {key}")
            return None

        logger.debug(f"Cache hit: {key}")
        return entry["value"]

    def set(self, key: str, value: Any, ttl: int = None):
        """Store a value in the cache.

        Args:
            key: Cache key.
            value: Value to cache.
            ttl: Optional override TTL for this entry.
        """
        self._store[key] = {
            "value": value,
            "timestamp": time.time(),
            "ttl": ttl or self.ttl,
        }
        logger.debug(f"Cache set: {key} (TTL={ttl or self.ttl}s)")

    def invalidate(self, key: str = None):
        """Invalidate a specific key or all cached data.

        Args:
            key: Specific key to invalidate. If None, clears all.
        """
        if key:
            self._store.pop(key, None)
            logger.debug(f"Cache invalidated: {key}")
        else:
            self._store.clear()
            logger.debug("Cache cleared")

    def make_key(self, category: str = None, time_hours: int = 24, extra: str = "") -> str:
        """Generate a cache key from query parameters.

        Args:
            category: Category filter.
            time_hours: Time range.
            extra: Any extra string to differentiate.

        Returns:
            Cache key string.
        """
        parts = [
            f"cat:{category or 'ALL'}",
            f"hours:{time_hours}",
        ]
        if extra:
            parts.append(f"extra:{extra}")
        return "|".join(parts)

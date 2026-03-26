"""
CacheManager: Thread-safe file ID cache management with TTL and size limits.

Manages Telegram file ID caching with automatic cleanup based on:
- Maximum entry count (LRU eviction)
- Time-to-live (TTL) for cache entries
"""

import json
import logging
import threading
import time
from collections import OrderedDict
from pathlib import Path

logger = logging.getLogger("ninova")


class CacheManager:
    """
    Thread-safe cache manager with TTL and size limits.

    Features:
    - Bounded cache (LRU eviction when full)
    - TTL-based expiration for entries
    - Atomic file persistence
    - Thread-safe operations with locking
    - Statistics and monitoring
    """

    # Class constants
    DEFAULT_MAX_ENTRIES = 10000  # Max cached file IDs
    DEFAULT_TTL_SECONDS = 7 * 24 * 3600  # 7 days
    CACHE_FILE = Path("data") / "file_cache.json"

    def __init__(
        self,
        cache_file: Path = CACHE_FILE,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ):
        """
        Initialize CacheManager.

        Args:
            cache_file: Path to persistent cache file
            max_entries: Maximum number of entries to keep (LRU eviction)
            ttl_seconds: Time-to-live for cache entries (seconds)
        """
        self._cache: OrderedDict = OrderedDict()  # {url: (file_id, timestamp)}
        self._lock = threading.Lock()
        self._cache_file = Path(cache_file)
        self._max_entries = max_entries
        self._ttl_seconds = ttl_seconds
        self._stats = {"hits": 0, "misses": 0, "evictions": 0}

        # Create cache directory if needed
        self._cache_file.parent.mkdir(parents=True, exist_ok=True)

        # Load existing cache from file
        self._load_from_file()
        logger.info(
            f"CacheManager initialized: max={max_entries}, ttl={ttl_seconds}s, "
            f"file={self._cache_file}, loaded={len(self._cache)} entries"
        )

    def get(self, key: str) -> str | None:
        """
        Get file ID from cache if exists and not expired.

        Args:
            key: Cache key (usually Ninova URL)

        Returns:
            File ID string if found and valid, None otherwise
        """
        with self._lock:
            if key not in self._cache:
                self._stats["misses"] += 1
                logger.debug(f"Cache miss: {key[:50]}...")
                return None

            file_id, timestamp = self._cache[key]
            current_time = time.time()

            # Check if entry expired
            if current_time - timestamp > self._ttl_seconds:
                del self._cache[key]
                self._stats["misses"] += 1
                logger.debug(f"Cache entry expired: {key[:50]}...")
                return None

            # Move to end (LRU tracking)
            self._cache.move_to_end(key)
            self._stats["hits"] += 1
            logger.debug(f"Cache hit: {key[:50]}...")

            return file_id

    def set(self, key: str, file_id: str) -> None:
        """
        Set file ID in cache.

        Args:
            key: Cache key (usually Ninova URL)
            file_id: Telegram file ID to cache
        """
        with self._lock:
            current_time = time.time()

            # If key exists, remove it first (to update position)
            if key in self._cache:
                del self._cache[key]

            # Check if we need to evict entries
            while len(self._cache) >= self._max_entries:
                evicted_key, _ = self._cache.popitem(last=False)  # Remove oldest
                self._stats["evictions"] += 1
                logger.debug(f"Evicted LRU cache entry: {evicted_key[:50]}...")

            # Add new entry
            self._cache[key] = (file_id, current_time)
            logger.debug(f"Cache set: {key[:50]}... (size: {len(self._cache)})")

    def clear_expired(self) -> int:
        """
        Remove all expired entries from cache.

        Returns:
            Number of entries removed
        """
        with self._lock:
            current_time = time.time()
            keys_to_remove = [
                key
                for key, (_, timestamp) in self._cache.items()
                if current_time - timestamp > self._ttl_seconds
            ]

            for key in keys_to_remove:
                del self._cache[key]

            if keys_to_remove:
                logger.info(f"Cleared {len(keys_to_remove)} expired cache entries")

            return len(keys_to_remove)

    def clear_all(self) -> None:
        """
        Clear entire cache.
        """
        with self._lock:
            self._cache.clear()
            logger.info("Cache cleared")

    def _load_from_file(self) -> None:
        """
        Load cache from persistent file.

        Handles old format (simple dict) and new format (with timestamps).
        """
        if not self._cache_file.exists():
            logger.debug(f"Cache file not found: {self._cache_file}")
            return

        try:
            with self._cache_file.open(encoding="utf-8") as f:
                data = json.load(f)

            # Check if data is new format (dict of lists) or old format (dict of strings)
            if data and isinstance(next(iter(data.values()), None), list):
                # New format: {key: [file_id, timestamp]}
                self._cache = OrderedDict((k, tuple(v)) for k, v in data.items())
            else:
                # Old format: {key: file_id} - add current timestamp
                current_time = time.time()
                self._cache = OrderedDict((k, (v, current_time)) for k, v in data.items())

            logger.info(f"Loaded {len(self._cache)} entries from cache file")
        except json.JSONDecodeError:
            logger.error(f"Cache file corrupted: {self._cache_file}")
            self._cache.clear()
        except Exception as e:
            logger.error(f"Error loading cache: {e}")
            self._cache.clear()

    def _save_to_file(self) -> None:
        """
        Save cache to persistent file (called by sync).

        Uses atomic write with temp file to prevent corruption.
        """
        try:
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)

            # Convert to JSON-serializable format
            data = {k: list(v) for k, v in self._cache.items()}

            # Write with temp file (atomic)
            temp_file = self._cache_file.with_suffix(".tmp")
            with temp_file.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            # Atomic move
            temp_file.replace(self._cache_file)
            logger.debug(f"Cache saved to file: {self._cache_file}")
        except Exception as e:
            logger.error(f"Error saving cache: {e}")

    def sync(self) -> None:
        """
        Synchronize cache to persistent file.

        Should be called periodically or when important entries are cached.
        """
        with self._lock:
            self._save_to_file()

    def stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        with self._lock:
            total_requests = self._stats["hits"] + self._stats["misses"]
            hit_rate = (self._stats["hits"] / total_requests * 100) if total_requests > 0 else 0

            return {
                "entries": len(self._cache),
                "max_entries": self._max_entries,
                "ttl_seconds": self._ttl_seconds,
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "hit_rate_percent": hit_rate,
                "evictions": self._stats["evictions"],
            }


# Global singleton instance
_cache_manager: CacheManager | None = None


def get_cache_manager(
    cache_file: Path = CacheManager.CACHE_FILE,
    max_entries: int = CacheManager.DEFAULT_MAX_ENTRIES,
    ttl_seconds: int = CacheManager.DEFAULT_TTL_SECONDS,
) -> CacheManager:
    """
    Get or create global CacheManager instance.

    Args:
        cache_file: Path to cache file
        max_entries: Max entries (only used if creating new instance)
        ttl_seconds: TTL in seconds (only used if creating new instance)

    Returns:
        Global CacheManager instance
    """
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager(
            cache_file=cache_file, max_entries=max_entries, ttl_seconds=ttl_seconds
        )
    return _cache_manager

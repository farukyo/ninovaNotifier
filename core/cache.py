"""LRU + TTL in-memory cache with periodic disk persistence.

migrated from: common/cache_manager.py
"""

# migrated from: common/cache_manager.py
from __future__ import annotations

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

    DEFAULT_MAX_ENTRIES = 10000
    DEFAULT_TTL_SECONDS = 7 * 24 * 3600
    CACHE_FILE = Path("data") / "file_cache.json"

    def __init__(
        self,
        cache_file: Path = CACHE_FILE,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ):
        self._cache: OrderedDict = OrderedDict()
        self._lock = threading.Lock()
        self._cache_file = Path(cache_file)
        self._max_entries = max_entries
        self._ttl_seconds = ttl_seconds
        self._stats = {"hits": 0, "misses": 0, "evictions": 0}

        self._cache_file.parent.mkdir(parents=True, exist_ok=True)
        self._load_from_file()
        logger.info(
            f"CacheManager initialized: max={max_entries}, ttl={ttl_seconds}s, "
            f"file={self._cache_file}, loaded={len(self._cache)} entries"
        )

    def get(self, key: str) -> str | None:
        with self._lock:
            if key not in self._cache:
                self._stats["misses"] += 1
                return None

            file_id, timestamp = self._cache[key]
            if time.time() - timestamp > self._ttl_seconds:
                del self._cache[key]
                self._stats["misses"] += 1
                return None

            self._cache.move_to_end(key)
            self._stats["hits"] += 1
            return file_id

    def set(self, key: str, file_id: str) -> None:
        with self._lock:
            if key in self._cache:
                del self._cache[key]

            while len(self._cache) >= self._max_entries:
                self._cache.popitem(last=False)
                self._stats["evictions"] += 1

            self._cache[key] = (file_id, time.time())

    def clear_expired(self) -> int:
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
        with self._lock:
            self._cache.clear()

    def _load_from_file(self) -> None:
        if not self._cache_file.exists():
            return
        try:
            with self._cache_file.open(encoding="utf-8") as f:
                data = json.load(f)
            if data and isinstance(next(iter(data.values()), None), list):
                self._cache = OrderedDict((k, tuple(v)) for k, v in data.items())
            else:
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
        try:
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            data = {k: list(v) for k, v in self._cache.items()}
            temp_file = self._cache_file.with_suffix(".tmp")
            with temp_file.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            temp_file.replace(self._cache_file)
        except Exception as e:
            logger.error(f"Error saving cache: {e}")

    def sync(self) -> None:
        with self._lock:
            self._save_to_file()

    def stats(self) -> dict:
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


_cache_manager: CacheManager | None = None


def get_cache_manager(
    cache_file: Path = CacheManager.CACHE_FILE,
    max_entries: int = CacheManager.DEFAULT_MAX_ENTRIES,
    ttl_seconds: int = CacheManager.DEFAULT_TTL_SECONDS,
) -> CacheManager:
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager(
            cache_file=cache_file, max_entries=max_entries, ttl_seconds=ttl_seconds
        )
    return _cache_manager

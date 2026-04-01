"""Tests for common/cache_manager.py — LRU eviction and TTL expiry."""

import time

import pytest

from common.cache_manager import CacheManager


@pytest.fixture
def cache(tmp_path):
    """Fresh CacheManager with small limits backed by a temp file."""
    cache_file = tmp_path / "test_cache.json"
    return CacheManager(cache_file=cache_file, max_entries=5, ttl_seconds=2)


class TestCacheManagerBasic:
    def test_set_and_get(self, cache):
        cache.set("key1", "file_id_abc")
        assert cache.get("key1") == "file_id_abc"

    def test_missing_key_returns_none(self, cache):
        assert cache.get("nonexistent") is None

    def test_overwrite_existing_key(self, cache):
        cache.set("k", "v1")
        cache.set("k", "v2")
        assert cache.get("k") == "v2"

    def test_clear_all(self, cache):
        cache.set("k", "v")
        cache.clear_all()
        assert cache.get("k") is None


class TestCacheManagerLRU:
    def test_lru_eviction_when_full(self, cache):
        for i in range(5):
            cache.set(f"key{i}", f"val{i}")
        # Adding one more must evict the oldest (key0)
        cache.set("key_new", "val_new")
        assert cache.get("key_new") == "val_new"
        assert cache.stats()["entries"] <= 5

    def test_eviction_count_tracked(self, cache):
        for i in range(6):
            cache.set(f"key{i}", f"val{i}")
        assert cache.stats()["evictions"] >= 1

    def test_access_updates_lru_order(self, cache):
        # Fill cache to max
        for i in range(5):
            cache.set(f"key{i}", f"val{i}")
        # Access key0 to move it to end (most recently used)
        cache.get("key0")
        # Add new entry — should evict key1, NOT key0
        cache.set("key_extra", "val_extra")
        assert cache.get("key0") == "val0"


class TestCacheManagerTTL:
    def test_fresh_entry_not_expired(self, cache):
        cache.set("fresh_key", "value")
        assert cache.get("fresh_key") == "value"

    def test_expired_entry_returns_none(self, cache):
        cache.set("ttl_key", "value")
        time.sleep(2.1)  # Wait past TTL (2s)
        assert cache.get("ttl_key") is None

    def test_clear_expired_removes_old_entries(self, cache):
        cache.set("old_key", "value")
        time.sleep(2.1)
        removed = cache.clear_expired()
        assert removed >= 1
        assert cache.get("old_key") is None


class TestCacheManagerStats:
    def test_hit_recorded(self, cache):
        cache.set("k", "v")
        cache.get("k")
        assert cache.stats()["hits"] == 1

    def test_miss_recorded(self, cache):
        cache.get("missing")
        assert cache.stats()["misses"] == 1

    def test_stats_keys_present(self, cache):
        stats = cache.stats()
        assert "entries" in stats
        assert "hits" in stats
        assert "misses" in stats
        assert "evictions" in stats
        assert "hit_rate_percent" in stats

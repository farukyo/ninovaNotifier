import logging
from common.cache_manager import get_cache_manager

logger = logging.getLogger("ninova")
_CACHE_MANAGER = get_cache_manager()


def load_file_cache():
    """Backward compatible no-op loader.

    Kept for legacy imports; CacheManager eagerly loads persisted cache.
    """
    return {}


def save_file_cache():
    """Backward compatible sync function."""
    _CACHE_MANAGER.sync()


def get_cached_file_id(ninova_url):
    return _CACHE_MANAGER.get(ninova_url)


def set_cached_file_id(ninova_url, file_id):
    _CACHE_MANAGER.set(ninova_url, file_id)
    _CACHE_MANAGER.sync()

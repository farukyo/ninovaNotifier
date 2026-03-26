import json
import logging
from pathlib import Path

logger = logging.getLogger("ninova")

CACHE_FILE = Path("data") / "file_cache.json"
_FILE_CACHE = {}


def load_file_cache():
    global _FILE_CACHE
    if not CACHE_FILE.exists():
        return {}
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with CACHE_FILE.open(encoding="utf-8") as f:
            _FILE_CACHE = json.load(f)
    except Exception as e:
        logger.error(f"Cache load error: {e}")
        _FILE_CACHE = {}
    return _FILE_CACHE


def save_file_cache():
    global _FILE_CACHE
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with CACHE_FILE.open("w", encoding="utf-8") as f:
            json.dump(_FILE_CACHE, f, indent=4)
    except Exception as e:
        logger.error(f"Cache save error: {e}")


def get_cached_file_id(ninova_url):
    global _FILE_CACHE
    if not _FILE_CACHE:
        load_file_cache()
    return _FILE_CACHE.get(ninova_url)


def set_cached_file_id(ninova_url, file_id):
    global _FILE_CACHE
    if not _FILE_CACHE:
        load_file_cache()
    _FILE_CACHE[ninova_url] = file_id
    save_file_cache()

import json
import os
from common.config import console

CACHE_FILE = "file_cache.json"
_FILE_CACHE = {}


def load_file_cache():
    global _FILE_CACHE
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            _FILE_CACHE = json.load(f)
    except Exception as e:
        console.print(f"[red]Cache yükleme hatası: {e}")
        _FILE_CACHE = {}
    return _FILE_CACHE


def save_file_cache():
    global _FILE_CACHE
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_FILE_CACHE, f, indent=4)
    except Exception as e:
        console.print(f"[red]Cache kaydetme hatası: {e}")


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

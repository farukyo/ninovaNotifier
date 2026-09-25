"""Small thread-safe TTL cache decorator for idempotent external fetches.

Arı24 kulüp listesi, haberler, SKS menüsü ve akademik takvim her buton basışında
yeniden çekiliyordu (Arı24 kulüp listesi tek başına ~21 istek). Bu dekoratör sonuçları
kısa süreliğine bellekte tutar. Boş/None sonuçlar (genelde hata demek) önbelleğe alınmaz,
böylece geçici bir hata TTL boyunca kalıcı hale gelmez.
"""

from __future__ import annotations

import copy
import functools
import threading
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


def ttl_cache(seconds: float, *, ignore_self: bool = False) -> Callable:
    """
    Fonksiyon sonucunu argümanlara göre `seconds` saniye önbelleğe alır.

    :param seconds: Önbellek süresi
    :param ignore_self: True ise ilk argüman (self) anahtara katılmaz; durumsuz
        client sınıflarının farklı örnekleri aynı önbelleği paylaşır.
    """

    def decorator(func: Callable) -> Callable:
        cache: dict[Any, tuple[float, Any]] = {}
        lock = threading.Lock()

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            key_args = args[1:] if ignore_self else args
            key = (key_args, tuple(sorted(kwargs.items())))
            now = time.monotonic()
            with lock:
                hit = cache.get(key)
                if hit is not None and now - hit[0] < seconds:
                    # Kopya döndür: çağıranın listeyi/dict'i değiştirmesi önbelleği bozmasın.
                    return copy.deepcopy(hit[1])
            result = func(*args, **kwargs)
            if result:
                with lock:
                    cache[key] = (time.monotonic(), copy.deepcopy(result))
            return result

        def cache_clear() -> None:
            with lock:
                cache.clear()

        wrapper.cache_clear = cache_clear  # type: ignore[attr-defined]
        return wrapper

    return decorator

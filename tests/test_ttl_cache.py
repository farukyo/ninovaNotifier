"""Tests for core/ttl_cache.py."""

from core import ttl_cache as ttl_module
from core.ttl_cache import ttl_cache


def test_caches_truthy_results_until_expiry(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(ttl_module.time, "monotonic", lambda: now[0])
    calls = []

    @ttl_cache(60)
    def fetch(x):
        calls.append(x)
        return [x]

    assert fetch(1) == [1]
    assert fetch(1) == [1]
    assert calls == [1]

    now[0] += 61
    assert fetch(1) == [1]
    assert calls == [1, 1]


def test_empty_results_are_not_cached():
    calls = []

    @ttl_cache(60)
    def fetch():
        calls.append(1)
        return []

    fetch()
    fetch()
    assert len(calls) == 2


def test_returns_copies_so_callers_cannot_corrupt_cache():
    @ttl_cache(60)
    def fetch():
        return [{"a": 1}]

    first = fetch()
    first[0]["a"] = 999
    first.append("junk")
    assert fetch() == [{"a": 1}]


def test_ignore_self_shares_cache_between_instances():
    calls = []

    class Client:
        @ttl_cache(60, ignore_self=True)
        def get(self, n):
            calls.append(n)
            return [n]

    Client().get(5)
    Client().get(5)
    assert calls == [5]

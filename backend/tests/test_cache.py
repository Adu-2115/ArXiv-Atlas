from app.services.cache import cache_get, cache_set


def test_cache_set_then_get_returns_value(tmp_cache_dir):
    cache_set("my-key", {"a": 1, "b": [1, 2, 3]})
    assert cache_get("my-key") == {"a": 1, "b": [1, 2, 3]}


def test_cache_get_missing_key_returns_none(tmp_cache_dir):
    assert cache_get("does-not-exist") is None


def test_cache_respects_ttl_expiry(tmp_cache_dir, monkeypatch):
    import time
    from app.services import cache as cache_module

    cache_set("expiring-key", "value", ttl_seconds=10)
    assert cache_get("expiring-key") == "value"

    # Simulate time passing beyond the TTL (capture real time first to
    # avoid the replacement function recursively calling itself).
    future_time = time.time() + 20
    monkeypatch.setattr(time, "time", lambda: future_time)
    assert cache_get("expiring-key") is None


def test_cache_none_ttl_never_expires(tmp_cache_dir, monkeypatch):
    import time

    cache_set("permanent-key", "value", ttl_seconds=None)
    future_time = time.time() + 60 * 60 * 24 * 365
    monkeypatch.setattr(time, "time", lambda: future_time)
    assert cache_get("permanent-key") == "value"


def test_cache_keys_are_isolated_by_content(tmp_cache_dir):
    cache_set("key-a", "value-a")
    cache_set("key-b", "value-b")
    assert cache_get("key-a") == "value-a"
    assert cache_get("key-b") == "value-b"

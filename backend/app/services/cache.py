"""
Lightweight disk-based cache, keyed by string, storing JSON-serializable
values with an optional TTL. No external dependencies — good enough for a
single-process local/small deployment. Swap for Redis if you ever need
multi-process or multi-instance caching.
"""
import hashlib
import json
import time
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / ".cache"
CACHE_DIR.mkdir(exist_ok=True)


def _key_path(key: str) -> Path:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{digest}.json"


def cache_get(key: str):
    """Returns the cached value, or None if missing/expired/corrupt."""
    path = _key_path(key)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    expires_at = payload.get("expires_at")
    if expires_at is not None and time.time() > expires_at:
        path.unlink(missing_ok=True)
        return None

    return payload.get("value")


def cache_set(key: str, value, ttl_seconds: int | None = None):
    """Stores value under key. ttl_seconds=None means it never expires."""
    path = _key_path(key)
    payload = {
        "value": value,
        "expires_at": (time.time() + ttl_seconds) if ttl_seconds else None,
    }
    try:
        path.write_text(json.dumps(payload), encoding="utf-8")
    except OSError:
        pass  # caching is best-effort; don't break the pipeline over a disk error


# Common TTLs, named for readability at call sites.
ONE_DAY = 60 * 60 * 24
ONE_WEEK = ONE_DAY * 7

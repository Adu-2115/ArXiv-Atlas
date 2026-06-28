"""
Shared pytest fixtures. Ensures GROQ_API_KEY has *some* value during tests
so app.config.get_settings() doesn't fail to construct — none of these
tests make real Groq calls, but importing service modules triggers
get_settings() at import time.
"""
import os
import pytest

os.environ.setdefault("GROQ_API_KEY", "test-key-not-real")


@pytest.fixture
def tmp_cache_dir(tmp_path, monkeypatch):
    """Redirects the disk cache to a temp dir so tests don't pollute/read the real .cache/."""
    from app.services import cache as cache_module

    monkeypatch.setattr(cache_module, "CACHE_DIR", tmp_path)
    return tmp_path

import httpx
from app.services import citations


def test_fetch_citation_counts_empty_input_returns_empty():
    assert citations.fetch_citation_counts([]) == {}


def test_fetch_citation_counts_success(monkeypatch, tmp_cache_dir):
    def fake_post(url, params=None, json=None, timeout=None):
        ids = json["ids"]
        # Echo back citation counts based on position for predictability.
        data = [{"citationCount": i * 10} for i in range(len(ids))]
        return httpx.Response(200, json=data, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)

    result = citations.fetch_citation_counts(["1234.5678", "2234.5678"])
    assert result == {"1234.5678": 0, "2234.5678": 10}


def test_fetch_citation_counts_handles_null_entries(monkeypatch, tmp_cache_dir):
    """Semantic Scholar returns null for IDs it doesn't recognize."""
    def fake_post(url, params=None, json=None, timeout=None):
        data = [None, {"citationCount": 5}]
        return httpx.Response(200, json=data, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)

    result = citations.fetch_citation_counts(["unknown.id", "known.id"])
    assert result == {"unknown.id": 0, "known.id": 5}


def test_fetch_citation_counts_defaults_to_zero_after_exhausting_retries(
    monkeypatch, tmp_cache_dir
):
    """Persistent 429s should exhaust retries and default to 0, not hang or crash."""
    call_count = 0

    def fake_post(url, params=None, json=None, timeout=None):
        nonlocal call_count
        call_count += 1
        return httpx.Response(429, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(citations.time, "sleep", lambda seconds: None)  # skip real delays

    result = citations.fetch_citation_counts(["1234.5678"])
    assert result == {"1234.5678": 0}
    assert call_count == citations.MAX_RETRIES


def test_fetch_citation_counts_retries_then_succeeds(monkeypatch, tmp_cache_dir):
    """A transient 429 followed by a 200 should succeed without giving up."""
    call_count = 0

    def fake_post(url, params=None, json=None, timeout=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(429, request=httpx.Request("POST", url))
        return httpx.Response(
            200, json=[{"citationCount": 7}], request=httpx.Request("POST", url)
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(citations.time, "sleep", lambda seconds: None)

    result = citations.fetch_citation_counts(["1234.5678"])
    assert result == {"1234.5678": 7}
    assert call_count == 2


def test_fetch_citation_counts_uses_cache(monkeypatch, tmp_cache_dir):
    call_count = 0

    def fake_post(url, params=None, json=None, timeout=None):
        nonlocal call_count
        call_count += 1
        data = [{"citationCount": 42}]
        return httpx.Response(200, json=data, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)

    citations.fetch_citation_counts(["1234.5678"])
    citations.fetch_citation_counts(["1234.5678"])  # second call should hit cache

    assert call_count == 1

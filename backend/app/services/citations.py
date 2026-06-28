"""
Citation-based ranking signal via the Semantic Scholar Graph API (free, no
API key required for low-volume use). Maps cleanly to arXiv IDs via the
"ARXIV:<id>" external ID format.

Semantic Scholar's unauthenticated tier has a tight, globally-shared rate
limit (~1 request/second recommended), so a 429 here is common and usually
resolves within a second or two — unlike Groq's daily token quota, retrying
is actually worthwhile. We retry a few times with backoff (respecting the
Retry-After header when present) before giving up and defaulting to 0.
This is a supporting signal, not a critical path — final failure never
breaks ranking, it just means citation_count=0 for that batch.
"""
import logging
import time
import httpx
from app.services.cache import ONE_WEEK, cache_get, cache_set

logger = logging.getLogger(__name__)

S2_BATCH_URL = "https://api.semanticscholar.org/graph/v1/paper/batch"
ONE_MONTH = ONE_WEEK * 4
MAX_RETRIES = 3


def _post_with_retry(ids_param: list[str]) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = httpx.post(
                S2_BATCH_URL,
                params={"fields": "citationCount"},
                json={"ids": ids_param},
                timeout=15.0,
            )
            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                wait_seconds = float(retry_after) if retry_after else (attempt + 1) * 1.5
                logger.info(
                    "Semantic Scholar rate limited, retrying",
                    extra={"attempt": attempt + 1, "wait_seconds": wait_seconds},
                )
                time.sleep(wait_seconds)
                continue
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError as e:
            last_error = e
            break  # non-429 HTTP error — retrying won't help, fail fast
        except Exception as e:
            last_error = e
            time.sleep((attempt + 1) * 1.0)

    raise last_error or RuntimeError("Semantic Scholar request failed after retries")


def fetch_citation_counts(arxiv_ids: list[str]) -> dict[str, int]:
    """Returns {arxiv_id: citation_count}. Missing/failed lookups default to 0."""
    if not arxiv_ids:
        return {}

    result: dict[str, int] = {}
    to_fetch: list[str] = []
    for aid in arxiv_ids:
        cached = cache_get(f"citations:v1:{aid}")
        if cached is not None:
            result[aid] = cached
        else:
            to_fetch.append(aid)

    if to_fetch:
        try:
            ids_param = [f"ARXIV:{aid}" for aid in to_fetch]
            resp = _post_with_retry(ids_param)
            data = resp.json()
            matched = 0
            for aid, paper in zip(to_fetch, data):
                count = (paper or {}).get("citationCount") or 0
                if paper is not None:
                    matched += 1
                result[aid] = count
                cache_set(f"citations:v1:{aid}", count, ttl_seconds=ONE_MONTH)
            logger.info(
                "Semantic Scholar: matched %d/%d papers", matched, len(to_fetch)
            )
        except httpx.HTTPStatusError as e:
            logger.warning(
                "Semantic Scholar citation lookup failed after retries (HTTP %s): %s — "
                "defaulting %d papers to citation_count=0",
                e.response.status_code, e, len(to_fetch),
            )
            for aid in to_fetch:
                result.setdefault(aid, 0)
        except Exception as e:
            logger.warning(
                "Semantic Scholar citation lookup failed after retries (%s) — "
                "defaulting %d papers to citation_count=0",
                e, len(to_fetch),
            )
            for aid in to_fetch:
                result.setdefault(aid, 0)

    return result

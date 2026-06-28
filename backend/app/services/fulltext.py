"""
Stage 3 helper: fetch and parse full paper text from ar5iv (the HTML
rendering of arXiv papers — much easier to parse reliably than raw PDF, and
has a fairly consistent <section>/<h2-4> heading structure to split on).

Used to upgrade extraction from abstract-only to full-text, which captures
nuance abstracts typically omit (exact limitations, precise dataset names).
Falls back to None on any failure so the caller can use the abstract instead
— this is a quality enhancement, not a critical-path dependency.
"""
import re
import httpx
from bs4 import BeautifulSoup
from app.services.cache import ONE_WEEK, cache_get, cache_set

# Headings whose section text we want to pull in for extraction. We
# deliberately skip "Introduction" (mostly motivation, already covered by
# the abstract) and "Related Work" (not about *this* paper's contribution).
SECTION_KEYWORDS = [
    "method", "methodology", "approach", "model", "architecture",
    "result", "experiment", "evaluation",
    "limitation", "discussion", "conclusion",
]

MAX_SECTION_CHARS = 1500   # cap per section so one huge section can't dominate
MAX_TOTAL_CHARS = 4000     # cap total full-text excerpt sent to the LLM


def fetch_fulltext_sections(arxiv_id: str, ar5iv_url: str) -> str | None:
    """
    Returns a condensed string of the paper's method/results/limitations
    sections, or None if fetching/parsing fails or no matching sections were
    found (caller should fall back to the abstract in that case).
    """
    cache_key = f"fulltext:v1:{arxiv_id}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached or None  # empty string cached means "previously failed"

    try:
        resp = httpx.get(ar5iv_url, timeout=20.0, follow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        sections = soup.find_all("section")
        collected: list[str] = []
        for sec in sections:
            heading = sec.find(["h2", "h3", "h4"])
            heading_text = heading.get_text(strip=True).lower() if heading else ""
            if any(kw in heading_text for kw in SECTION_KEYWORDS):
                text = sec.get_text(separator=" ", strip=True)
                text = re.sub(r"\s+", " ", text)
                collected.append(text[:MAX_SECTION_CHARS])

        result = " ".join(collected)[:MAX_TOTAL_CHARS] if collected else ""
        cache_set(cache_key, result, ttl_seconds=ONE_WEEK)
        return result or None
    except Exception:
        # Cache the failure too (briefly) so a consistently-broken ar5iv page
        # doesn't get re-fetched on every single run for the same paper.
        cache_set(cache_key, "", ttl_seconds=ONE_WEEK)
        return None

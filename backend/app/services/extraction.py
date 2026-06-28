"""
Stage 3: Extract insights.

Two upgrades over the original abstract-only version:

1. Full-text extraction via ar5iv. We try to fetch and parse the paper's
   method/results/limitations sections from ar5iv's HTML rendering (much
   easier to parse than raw PDF). If that fails for any reason, we fall back
   to the abstract — this is a quality enhancement, not a hard dependency.

2. True async concurrency. Extraction is I/O-bound (waiting on Groq's API),
   so asyncio + a semaphore gives the same concurrency as a thread pool with
   less overhead, and composes more naturally with the rest of the now-async
   pipeline.

Skip-and-backfill is unchanged in spirit: if extraction fails for a paper
(rate limit, transient error), it is NOT retried. The next-ranked paper is
pulled in to fill its slot instead, since retrying the same call is unlikely
to behave differently and just burns more time/quota.
"""
import asyncio
from app.config import get_settings
from app.models.schemas import PaperInsights, RankedPaper
from app.services.cache import cache_get, cache_set
from app.services.fulltext import fetch_fulltext_sections
from app.services.groq_client import async_chat_json

settings = get_settings()

_EXTRACTION_SYSTEM = (
    "You extract structured information from research papers. Be precise "
    "and concise; do not invent details not supported by the text."
)

_EXTRACTION_FAILED_MARKER = "Extraction failed"

# Cache key version bumped (v1 -> v2) since the extraction input changed
# (full-text + abstract, not abstract-only) — old cached abstract-only
# extractions shouldn't be silently reused as if they were full-text ones.
_CACHE_VERSION = "v2"


async def _extract_one(paper: RankedPaper, semaphore: asyncio.Semaphore) -> PaperInsights:
    cache_key = f"extraction:{_CACHE_VERSION}:{paper.arxiv_id}"
    cached = cache_get(cache_key)
    if cached is not None:
        return PaperInsights(**cached)

    # Prefer full-text sections from ar5iv; fall back to the abstract alone.
    source_text = f"Abstract: {paper.abstract}"
    if paper.ar5iv_url:
        fulltext = await asyncio.to_thread(
            fetch_fulltext_sections, paper.arxiv_id, paper.ar5iv_url
        )
        if fulltext:
            source_text = f"Abstract: {paper.abstract}\n\nFull text excerpts: {fulltext}"

    user = (
        f"Title: {paper.title}\n"
        f"{source_text}\n\n"
        "Extract the following as JSON:\n"
        "{\n"
        '  "problem": "what problem this paper addresses (1-2 sentences)",\n'
        '  "method": "what approach/method they propose (1-2 sentences)",\n'
        '  "key_results": ["result 1", "result 2"],\n'
        '  "datasets_benchmarks": ["dataset/benchmark names mentioned, or empty list"],\n'
        '  "limitations": "stated or inferable limitations, or null"\n'
        "}"
    )

    async with semaphore:
        try:
            data = await async_chat_json(
                _EXTRACTION_SYSTEM, user, model=settings.groq_extraction_model
            )
            insight = PaperInsights(
                arxiv_id=paper.arxiv_id,
                title=paper.title,
                problem=data.get("problem", "Not specified"),
                method=data.get("method", "Not specified"),
                key_results=data.get("key_results", []) or [],
                datasets_benchmarks=data.get("datasets_benchmarks", []) or [],
                limitations=data.get("limitations"),
            )
            # Only cache successful extractions — a transient failure
            # shouldn't be cached as if it were the permanent answer.
            cache_set(cache_key, insight.model_dump(), ttl_seconds=None)
            return insight
        except Exception as e:
            return PaperInsights(
                arxiv_id=paper.arxiv_id,
                title=paper.title,
                problem=_EXTRACTION_FAILED_MARKER,
                method=_EXTRACTION_FAILED_MARKER,
                key_results=[],
                datasets_benchmarks=[],
                limitations=f"error: {e}",
            )


async def extract_with_backfill(
    ranked_papers: list[RankedPaper],
    target_count: int,
    max_concurrency: int = 3,
) -> tuple[list[RankedPaper], list[PaperInsights]]:
    """
    Attempts extraction on the top `target_count` papers concurrently (via
    asyncio, bounded by `max_concurrency`). Any paper that fails is dropped
    (not retried); we backfill its slot from the next-ranked papers in the
    pool, one at a time, until we reach target_count successes or exhaust
    the pool.

    Returns (papers, insights) in matching order, both trimmed to whatever
    actually succeeded (could be < target_count if the whole pool runs out).
    """
    if not ranked_papers:
        return [], []

    semaphore = asyncio.Semaphore(max_concurrency)
    primary_batch = ranked_papers[:target_count]
    backfill_pool = ranked_papers[target_count:]

    successes: list[tuple[RankedPaper, PaperInsights]] = []

    results = await asyncio.gather(*[_extract_one(p, semaphore) for p in primary_batch])
    for paper, insight in zip(primary_batch, results):
        if insight.problem != _EXTRACTION_FAILED_MARKER:
            successes.append((paper, insight))
        # Failed papers are simply dropped — no retry on the same paper.

    # Sequentially backfill from the remaining pool until we hit target_count.
    backfill_iter = iter(backfill_pool)
    while len(successes) < target_count:
        next_paper = next(backfill_iter, None)
        if next_paper is None:
            break  # pool exhausted, return what we have
        insight = await _extract_one(next_paper, semaphore)
        if insight.problem != _EXTRACTION_FAILED_MARKER:
            successes.append((next_paper, insight))

    # Preserve original ranked order rather than completion/backfill order.
    order = {p.arxiv_id: i for i, p in enumerate(ranked_papers)}
    successes.sort(key=lambda pair: order.get(pair[0].arxiv_id, len(ranked_papers)))

    papers = [p for p, _ in successes]
    insights = [i for _, i in successes]
    return papers, insights

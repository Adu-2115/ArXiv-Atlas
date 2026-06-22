"""
Stage 3: Extract insights.

Abstract-only extraction for now (fast, no PDF parsing). Each paper is sent
to the LLM individually with a fixed schema prompt; this keeps failures
isolated to one paper instead of one big batched call breaking everything.

Two reliability/cost features:
1. Caching — extraction results are cached per arxiv_id, since a paper's
   abstract never changes. Re-running the same topic (or a different topic
   that happens to surface the same paper) costs zero extra LLM calls for
   papers already extracted.
2. Skip-and-backfill — if extraction fails for a paper (e.g. transient rate
   limit), we do NOT retry that paper. Instead we pull the next paper down
   the ranked list to fill its slot. This avoids wasting calls retrying a
   paper that may keep failing, and uses the ranking we already computed.

NOTE: to upgrade to full-text extraction later, fetch the ar5iv_url HTML
(much easier to parse than raw PDF) and pass the body text instead of the
abstract below.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.config import get_settings
from app.models.schemas import PaperInsights, RankedPaper
from app.services.cache import cache_get, cache_set
from app.services.groq_client import chat_json

settings = get_settings()

_EXTRACTION_SYSTEM = (
    "You extract structured information from research paper abstracts. "
    "Be precise and concise; do not invent details not supported by the text."
)

_EXTRACTION_FAILED_MARKER = "Extraction failed"


def _extract_one(paper: RankedPaper) -> PaperInsights:
    """Extract insights for a single paper, using the cache when available."""
    cache_key = f"extraction:v1:{paper.arxiv_id}"
    cached = cache_get(cache_key)
    if cached is not None:
        return PaperInsights(**cached)

    user = (
        f"Title: {paper.title}\n"
        f"Abstract: {paper.abstract}\n\n"
        "Extract the following as JSON:\n"
        "{\n"
        '  "problem": "what problem this paper addresses (1-2 sentences)",\n'
        '  "method": "what approach/method they propose (1-2 sentences)",\n'
        '  "key_results": ["result 1", "result 2"],\n'
        '  "datasets_benchmarks": ["dataset/benchmark names mentioned, or empty list"],\n'
        '  "limitations": "stated or inferable limitations, or null"\n'
        "}"
    )
    try:
        data = chat_json(
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
        # Only cache successful extractions — a transient failure shouldn't
        # be cached as if it were the permanent answer for this paper.
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


def extract_with_backfill(
    ranked_papers: list[RankedPaper],
    target_count: int,
    max_workers: int = 3,
) -> tuple[list[RankedPaper], list[PaperInsights]]:
    """
    Attempts extraction on the top `target_count` papers concurrently. Any
    paper that fails is dropped (not retried); we backfill its slot from the
    next-ranked papers in the pool, one at a time, until we reach
    target_count successes or exhaust the pool.

    Returns (papers, insights) in matching order, both trimmed to whatever
    actually succeeded (could be < target_count if the whole pool runs out).
    """
    if not ranked_papers:
        return [], []

    primary_batch = ranked_papers[:target_count]
    backfill_pool = ranked_papers[target_count:]

    successes: list[tuple[RankedPaper, PaperInsights]] = []

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_extract_one, p): p for p in primary_batch}
        for future in as_completed(futures):
            paper = futures[future]
            insight = future.result()
            if insight.problem != _EXTRACTION_FAILED_MARKER:
                successes.append((paper, insight))
            # Failed papers are simply dropped — no retry on the same paper.

    # Sequentially backfill from the remaining pool until we hit target_count.
    backfill_iter = iter(backfill_pool)
    while len(successes) < target_count:
        next_paper = next(backfill_iter, None)
        if next_paper is None:
            break  # pool exhausted, return what we have
        insight = _extract_one(next_paper)
        if insight.problem != _EXTRACTION_FAILED_MARKER:
            successes.append((next_paper, insight))

    # Preserve original ranked order rather than completion/backfill order.
    order = {p.arxiv_id: i for i, p in enumerate(ranked_papers)}
    successes.sort(key=lambda pair: order.get(pair[0].arxiv_id, len(ranked_papers)))

    papers = [p for p, _ in successes]
    insights = [i for _, i in successes]
    return papers, insights

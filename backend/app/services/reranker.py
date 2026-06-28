"""
Stage 2: Rank papers.

Pipeline within this stage:
1. Cross-encoder (local, fast, cheap) scores topic-vs-abstract relevance for
   every candidate. We keep the top `cross_encoder_top_k`.
2. LLM (Groq) does a finer-grained judgment call on that shortlist, scoring
   relevance 0-100 and giving a one-line justification.
3. Citation counts (Semantic Scholar) and recency are blended in to produce
   a final_score, so a well-cited foundational paper isn't outranked purely
   by an obscure-but-textually-similar one.
4. MMR diversity reranking reorders the list so the final "top N" taken
   downstream spans different sub-approaches instead of clustering around
   one phrasing/angle on the topic.

Returns the FULL scored+reordered shortlist (up to cross_encoder_top_k), not
sliced to final_paper_count — extraction (stage 3) decides how many to keep
and draws replacements from the rest of this list on failure.
"""
from datetime import datetime, timezone
from functools import lru_cache
from sentence_transformers import CrossEncoder
from app.config import get_settings
from app.models.schemas import ArxivPaper, RankedPaper
from app.services.cache import ONE_DAY, cache_get, cache_set
from app.services.citations import fetch_citation_counts
from app.services.diversity import mmr_rerank
from app.services.groq_client import chat_json

settings = get_settings()


@lru_cache
def _get_cross_encoder() -> CrossEncoder:
    return CrossEncoder(settings.cross_encoder_model)


def cross_encoder_rank(topic: str, papers: list[ArxivPaper]) -> list[tuple[ArxivPaper, float]]:
    if not papers:
        return []
    model = _get_cross_encoder()
    pairs = [(topic, p.abstract) for p in papers]
    scores = model.predict(pairs)
    scored = list(zip(papers, [float(s) for s in scores]))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[: settings.cross_encoder_top_k]


def llm_relevance_pass(topic: str, scored: list[tuple[ArxivPaper, float]]) -> list[RankedPaper]:
    """LLM relevance score (0-100) + one-line justification, cached per (topic, paper set)."""
    if not scored:
        return []

    paper_ids = sorted(p.arxiv_id for p, _ in scored)
    cache_key = f"llm_relevance:v1:{topic.strip().lower()}:{','.join(paper_ids)}"
    cached = cache_get(cache_key)

    if cached is None:
        paper_list_text = "\n\n".join(
            f"[{i}] arxiv_id={p.arxiv_id}\nTitle: {p.title}\nAbstract: {p.abstract[:400]}"
            for i, (p, _) in enumerate(scored)
        )
        system = (
            "You are a research assistant judging paper relevance. For each "
            "paper, score how directly relevant it is to the given topic "
            "(0-100) and give a one-sentence justification."
        )
        user = (
            f'Topic: "{topic}"\n\n'
            f"Papers:\n{paper_list_text}\n\n"
            'Return JSON: {"results": [{"index": 0, "relevance_score": 85, '
            '"justification": "..."}, ...]} for every paper index above.'
        )
        try:
            result = chat_json(system, user, max_tokens=4096)
            score_map = {r["index"]: r for r in result.get("results", [])}
        except Exception:
            score_map = {}
        cache_set(cache_key, score_map, ttl_seconds=ONE_DAY)
    else:
        score_map = {int(k): v for k, v in cached.items()}  # JSON round-trip stringifies int keys

    ranked: list[RankedPaper] = []
    for i, (paper, ce_score) in enumerate(scored):
        llm_info = score_map.get(i, {})
        ranked.append(
            RankedPaper(
                **paper.model_dump(),
                cross_encoder_score=ce_score,
                llm_relevance_score=llm_info.get("relevance_score"),
                llm_justification=llm_info.get("justification"),
            )
        )
    return ranked


def _normalize(values: list[float]) -> list[float]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi == lo:
        return [0.5 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


def _recency_score(published: str | None) -> float:
    """Newer papers score closer to 1.0; older/missing dates score lower."""
    if not published:
        return 0.0
    try:
        year = int(published[:4])
        current_year = datetime.now(timezone.utc).year
        age = max(current_year - year, 0)
        return max(0.0, 1.0 - (age / 10))  # linear falloff over ~10 years
    except (ValueError, TypeError):
        return 0.0


def blend_final_scores(ranked: list[RankedPaper]) -> list[RankedPaper]:
    """
    Combines LLM relevance + citation count + recency into a single
    final_score per paper, using configurable weights. Citation counts are
    fetched live (cached for a month per arxiv_id) from Semantic Scholar.
    """
    if not ranked:
        return ranked

    citation_counts = fetch_citation_counts([p.arxiv_id for p in ranked])

    relevance_raw = [
        p.llm_relevance_score if p.llm_relevance_score is not None else p.cross_encoder_score * 100
        for p in ranked
    ]
    citation_raw = [float(citation_counts.get(p.arxiv_id, 0)) for p in ranked]
    recency_raw = [_recency_score(p.published) for p in ranked]

    relevance_norm = _normalize(relevance_raw)
    citation_norm = _normalize(citation_raw)
    # Recency is already 0-1 by construction, no need to re-normalize.

    updated: list[RankedPaper] = []
    for paper, rel, cite, rec, cite_count in zip(
        ranked, relevance_norm, citation_norm, recency_raw, citation_raw
    ):
        final = (
            settings.relevance_weight * rel
            + settings.citation_weight * cite
            + settings.recency_weight * rec
        )
        updated.append(
            paper.model_copy(update={"citation_count": int(cite_count), "final_score": final})
        )

    updated.sort(key=lambda p: p.final_score or 0, reverse=True)
    return updated


def rank_papers(topic: str, papers: list[ArxivPaper]) -> list[RankedPaper]:
    """Returns the full ranked shortlist (up to cross_encoder_top_k papers)."""
    shortlist = cross_encoder_rank(topic, papers)
    ranked = llm_relevance_pass(topic, shortlist)
    ranked = blend_final_scores(ranked)
    ranked = mmr_rerank(ranked)
    return ranked

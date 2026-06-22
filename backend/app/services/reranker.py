"""
Stage 2: Rank papers.

Two passes:
1. Cross-encoder (local, fast, cheap) scores topic-vs-abstract relevance for
   every candidate. We keep the top `cross_encoder_top_k`.
2. LLM (Groq) does a finer-grained judgment call on that shortlist, scoring
   relevance 0-100 and giving a one-line justification — this is what gets
   shown in the UI next to each selected paper.

NOTE: this returns the FULL scored shortlist (up to cross_encoder_top_k), not
sliced to final_paper_count. Extraction (stage 3) decides how many to keep,
since it needs a buffer pool to draw replacements from when extraction fails
on a given paper, instead of retrying the same paper.
"""
from functools import lru_cache
from sentence_transformers import CrossEncoder
from app.config import get_settings
from app.models.schemas import ArxivPaper, RankedPaper
from app.services.cache import ONE_DAY, cache_get, cache_set
from app.services.groq_client import chat_json

settings = get_settings()


@lru_cache
def _get_cross_encoder() -> CrossEncoder:
    # Cached so the model loads once per process, not once per request.
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
    """
    Send the cross-encoder shortlist to the LLM in one batched call for a
    relevance score (0-100) + short justification per paper. Cached by
    (topic, exact set of arxiv_ids) since the same shortlist for the same
    topic should score the same way.
    """
    if not scored:
        return []

    paper_ids = sorted(p.arxiv_id for p, _ in scored)
    cache_key = f"llm_relevance:v1:{topic.strip().lower()}:{','.join(paper_ids)}"
    cached = cache_get(cache_key)

    if cached is None:
        paper_list_text = "\n\n".join(
            f"[{i}] arxiv_id={p.arxiv_id}\nTitle: {p.title}\nAbstract: {p.abstract[:600]}"
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
        # JSON round-trip turns int keys into strings; normalize back.
        score_map = {int(k): v for k, v in cached.items()}

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

    # Prefer LLM score when available, fall back to cross-encoder score.
    ranked.sort(
        key=lambda r: r.llm_relevance_score
        if r.llm_relevance_score is not None
        else r.cross_encoder_score,
        reverse=True,
    )
    return ranked


def rank_papers(topic: str, papers: list[ArxivPaper]) -> list[RankedPaper]:
    """Returns the full ranked shortlist (up to cross_encoder_top_k papers)."""
    shortlist = cross_encoder_rank(topic, papers)
    return llm_relevance_pass(topic, shortlist)

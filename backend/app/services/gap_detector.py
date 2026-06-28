"""
Research Gap Detector.

A single additional LLM call over the structured extractions already
produced in stage 3 — no new data collection needed. Surfaces underexplored
directions, conflicting findings, missing benchmarks, and concrete
future-work ideas, grounded in the actual retrieved papers rather than the
model's general knowledge of the field (which risks confident-sounding but
ungrounded claims).
"""
from app.models.schemas import PaperInsights, RankedPaper, ResearchGaps
from app.services.cache import ONE_DAY, cache_get, cache_set
from app.services.groq_client import async_chat_json

_SYSTEM = (
    "You are a research analyst identifying gaps and opportunities across a "
    "set of papers. Ground every claim in the specific papers provided — do "
    "not speculate beyond what they support, and do not give generic AI "
    "research advice that could apply to any topic."
)


def _build_block(paper: RankedPaper, insight: PaperInsights) -> str:
    return (
        f"title: {paper.title}\n"
        f"problem: {insight.problem}\n"
        f"method: {insight.method}\n"
        f"limitations: {insight.limitations or 'none stated'}\n"
        f"datasets: {', '.join(insight.datasets_benchmarks) or 'none listed'}"
    )


async def detect_research_gaps(
    topic: str, papers: list[RankedPaper], insights: list[PaperInsights]
) -> ResearchGaps:
    insight_by_id = {i.arxiv_id: i for i in insights}
    relevant_papers = [p for p in papers if p.arxiv_id in insight_by_id]

    if not relevant_papers:
        return ResearchGaps()

    paper_ids = sorted(p.arxiv_id for p in relevant_papers)
    cache_key = f"research_gaps:v1:{topic.strip().lower()}:{','.join(paper_ids)}"
    cached = cache_get(cache_key)
    if cached is not None:
        return ResearchGaps(**cached)

    blocks = "\n---\n".join(
        _build_block(p, insight_by_id[p.arxiv_id]) for p in relevant_papers
    )

    user = (
        f'Topic: "{topic}"\n\nPapers:\n{blocks}\n\n'
        "Based only on these papers, identify research gaps as JSON:\n"
        "{\n"
        '  "underexplored_directions": ["..."],\n'
        '  "conflicting_findings": ["..."],\n'
        '  "missing_benchmarks": ["..."],\n'
        '  "future_work": ["..."]\n'
        "}\n"
        "2-4 specific items per list, each referencing what these particular "
        "papers do or don't cover. If a category genuinely doesn't apply "
        "(e.g. no conflicting findings among these papers), return an empty "
        "list for it rather than inventing one."
    )

    try:
        data = await async_chat_json(_SYSTEM, user, max_tokens=2048, temperature=0.3)
    except Exception:
        data = {}

    gaps = ResearchGaps(
        underexplored_directions=data.get("underexplored_directions", []) or [],
        conflicting_findings=data.get("conflicting_findings", []) or [],
        missing_benchmarks=data.get("missing_benchmarks", []) or [],
        future_work=data.get("future_work", []) or [],
    )
    cache_set(cache_key, gaps.model_dump(), ttl_seconds=ONE_DAY)
    return gaps

"""
Standalone async orchestrator for the full pipeline — kept for scripting/
testing outside the API (e.g. a one-off script). The actual API routes in
routers/research.py inline this same sequence themselves so they can emit
per-stage SSE events; this module is the non-streaming equivalent.
"""
import asyncio
from app.config import get_settings
from app.models.schemas import PipelineResult
from app.services import history
from app.services.arxiv_search import find_papers
from app.services.extraction import extract_with_backfill
from app.services.gap_detector import detect_research_gaps
from app.services.reranker import rank_papers
from app.services.synthesis import build_research_map

settings = get_settings()


async def run_pipeline(topic: str) -> PipelineResult:
    candidates = await asyncio.to_thread(find_papers, topic)
    ranked_pool = await asyncio.to_thread(rank_papers, topic, candidates)
    ranked_pool = [
        p
        for p in ranked_pool
        if p.llm_relevance_score is None or p.llm_relevance_score >= settings.min_relevance_score
    ]
    final_papers, insights = await extract_with_backfill(
        ranked_pool, target_count=settings.final_paper_count
    )
    research_map = await asyncio.to_thread(build_research_map, topic, final_papers, insights)
    research_gaps = await detect_research_gaps(topic, final_papers, insights)

    result = PipelineResult(
        topic=topic,
        candidates_found=len(candidates),
        ranked_papers=final_papers,
        insights=insights,
        research_map=research_map,
        research_gaps=research_gaps,
    )
    await asyncio.to_thread(history.save_run, topic, result)
    return result

"""
Orchestrates the four pipeline stages:
find_papers -> rank_papers -> extract_with_backfill -> build_research_map

Extraction targets `final_paper_count` successes, backfilling from the
ranked pool when a given paper's extraction fails (instead of retrying it).
"""
from app.config import get_settings
from app.models.schemas import PipelineResult
from app.services.arxiv_search import find_papers
from app.services.extraction import extract_with_backfill
from app.services.reranker import rank_papers
from app.services.synthesis import build_research_map

settings = get_settings()


def run_pipeline(topic: str) -> PipelineResult:
    candidates = find_papers(topic)
    ranked_pool = rank_papers(topic, candidates)
    final_papers, insights = extract_with_backfill(
        ranked_pool, target_count=settings.final_paper_count
    )
    research_map = build_research_map(topic, final_papers, insights)

    return PipelineResult(
        topic=topic,
        candidates_found=len(candidates),
        ranked_papers=final_papers,
        insights=insights,
        research_map=research_map,
    )

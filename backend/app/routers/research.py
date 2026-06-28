"""
Research router.

Exposes:
- POST /api/research        -> blocking, returns the full PipelineResult
- POST /api/research/stream -> Server-Sent Events, emits progress per stage

Stages that are CPU/network-bound but synchronous (arxiv search, ranking,
synthesis) run via asyncio.to_thread so they don't block the event loop.
Extraction and gap detection are natively async (concurrent Groq calls).
Every completed run is saved to SQLite search history. Each stage's
duration is logged (structured JSON logs) so slow stages are visible
without needing to add print statements while debugging.
"""
import asyncio
import json
import logging
import time
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.config import get_settings
from app.models.schemas import PipelineResult, TopicRequest
from app.services import history
from app.services.arxiv_search import find_papers
from app.services.extraction import extract_with_backfill
from app.services.gap_detector import detect_research_gaps
from app.services.reranker import rank_papers
from app.services.synthesis import build_research_map

router = APIRouter(prefix="/api/research", tags=["research"])
settings = get_settings()
logger = logging.getLogger(__name__)


def _filter_by_relevance(ranked_pool):
    """
    Drops papers below min_relevance_score entirely — backfill should never
    pad the final set with papers the LLM itself flagged as irrelevant just
    to hit final_paper_count. Returning fewer than final_paper_count for a
    niche/unusual topic is more honest than padding with noise.
    """
    return [
        p
        for p in ranked_pool
        if p.llm_relevance_score is None or p.llm_relevance_score >= settings.min_relevance_score
    ]


class _StageTimer:
    """Small context manager that logs a stage's duration on exit."""

    def __init__(self, stage: str, topic: str):
        self.stage = stage
        self.topic = topic

    def __enter__(self):
        self.start = time.perf_counter()
        logger.info("stage started", extra={"stage": self.stage, "topic": self.topic})
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = round((time.perf_counter() - self.start) * 1000)
        if exc_type is None:
            logger.info(
                "stage completed",
                extra={"stage": self.stage, "topic": self.topic, "duration_ms": duration_ms},
            )
        else:
            logger.error(
                "stage failed",
                extra={
                    "stage": self.stage,
                    "topic": self.topic,
                    "duration_ms": duration_ms,
                    "error": str(exc_val),
                },
            )
        return False  # never swallow exceptions


async def _run_pipeline(topic: str) -> PipelineResult:
    with _StageTimer("find_papers", topic):
        candidates = await asyncio.to_thread(find_papers, topic)
    with _StageTimer("rank_papers", topic):
        ranked_pool = await asyncio.to_thread(rank_papers, topic, candidates)
    ranked_pool = _filter_by_relevance(ranked_pool)
    with _StageTimer("extract_insights", topic):
        final_papers, insights = await extract_with_backfill(
            ranked_pool, target_count=settings.final_paper_count
        )
    with _StageTimer("map_research", topic):
        research_map = await asyncio.to_thread(build_research_map, topic, final_papers, insights)
    with _StageTimer("detect_gaps", topic):
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


@router.post("", response_model=PipelineResult)
async def research(req: TopicRequest) -> PipelineResult:
    return await _run_pipeline(req.topic)


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/stream")
async def research_stream(req: TopicRequest):
    async def event_generator():
        topic = req.topic
        try:
            yield _sse_event("stage", {"stage": "find_papers", "status": "started"})
            with _StageTimer("find_papers", topic):
                candidates = await asyncio.to_thread(find_papers, topic)
            yield _sse_event(
                "stage",
                {"stage": "find_papers", "status": "done", "count": len(candidates)},
            )

            yield _sse_event("stage", {"stage": "rank_papers", "status": "started"})
            with _StageTimer("rank_papers", topic):
                ranked_pool = await asyncio.to_thread(rank_papers, topic, candidates)
            ranked_pool = _filter_by_relevance(ranked_pool)
            yield _sse_event("stage", {"stage": "rank_papers", "status": "done"})

            yield _sse_event("stage", {"stage": "extract_insights", "status": "started"})
            with _StageTimer("extract_insights", topic):
                final_papers, insights = await extract_with_backfill(
                    ranked_pool, target_count=settings.final_paper_count
                )
            yield _sse_event(
                "stage",
                {
                    "stage": "extract_insights",
                    "status": "done",
                    "papers": [p.model_dump() for p in final_papers],
                    "insights": [i.model_dump() for i in insights],
                },
            )

            yield _sse_event("stage", {"stage": "map_research", "status": "started"})
            with _StageTimer("map_research", topic):
                research_map = await asyncio.to_thread(
                    build_research_map, topic, final_papers, insights
                )
            yield _sse_event(
                "stage",
                {"stage": "map_research", "status": "done", "map": research_map.model_dump()},
            )

            yield _sse_event("stage", {"stage": "detect_gaps", "status": "started"})
            with _StageTimer("detect_gaps", topic):
                research_gaps = await detect_research_gaps(topic, final_papers, insights)
            yield _sse_event(
                "stage",
                {"stage": "detect_gaps", "status": "done", "gaps": research_gaps.model_dump()},
            )

            result = PipelineResult(
                topic=topic,
                candidates_found=len(candidates),
                ranked_papers=final_papers,
                insights=insights,
                research_map=research_map,
                research_gaps=research_gaps,
            )
            await asyncio.to_thread(history.save_run, topic, result)

            yield _sse_event("complete", {"status": "complete"})
        except Exception as e:
            logger.error("pipeline failed", extra={"topic": topic, "error": str(e)})
            yield _sse_event("error", {"message": str(e)})

    return StreamingResponse(event_generator(), media_type="text/event-stream")

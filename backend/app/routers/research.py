"""
Research router.

Exposes:
- POST /api/research        -> blocking, returns the full PipelineResult
- POST /api/research/stream -> Server-Sent Events, emits progress per stage
                                so the frontend can show "Searching arXiv...",
                                "Ranking papers...", etc. and render partial
                                results as they arrive.
"""
import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.config import get_settings
from app.models.schemas import PipelineResult, TopicRequest
from app.services.arxiv_search import find_papers
from app.services.extraction import extract_with_backfill
from app.services.reranker import rank_papers
from app.services.synthesis import build_research_map

router = APIRouter(prefix="/api/research", tags=["research"])
settings = get_settings()


@router.post("", response_model=PipelineResult)
def research(req: TopicRequest) -> PipelineResult:
    candidates = find_papers(req.topic)
    ranked_pool = rank_papers(req.topic, candidates)
    final_papers, insights = extract_with_backfill(
        ranked_pool, target_count=settings.final_paper_count
    )
    research_map = build_research_map(req.topic, final_papers, insights)
    return PipelineResult(
        topic=req.topic,
        candidates_found=len(candidates),
        ranked_papers=final_papers,
        insights=insights,
        research_map=research_map,
    )


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/stream")
def research_stream(req: TopicRequest):
    def event_generator():
        topic = req.topic

        yield _sse_event("stage", {"stage": "find_papers", "status": "started"})
        candidates = find_papers(topic)
        yield _sse_event(
            "stage",
            {"stage": "find_papers", "status": "done", "count": len(candidates)},
        )

        yield _sse_event("stage", {"stage": "rank_papers", "status": "started"})
        ranked_pool = rank_papers(topic, candidates)
        # The frontend shows the final selected set, not the wider ranked
        # pool — that's only resolved once extraction (with backfill) runs.
        yield _sse_event("stage", {"stage": "rank_papers", "status": "done"})

        yield _sse_event("stage", {"stage": "extract_insights", "status": "started"})
        final_papers, insights = extract_with_backfill(
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
        research_map = build_research_map(topic, final_papers, insights)
        yield _sse_event(
            "stage",
            {"stage": "map_research", "status": "done", "map": research_map.model_dump()},
        )

        yield _sse_event("complete", {"status": "complete"})

    return StreamingResponse(event_generator(), media_type="text/event-stream")

"""
Tests for extract_with_backfill's core behavior: failed papers are dropped
(not retried) and replaced from the remaining ranked pool, preserving
original rank order among whatever ultimately succeeds.

We monkeypatch _extract_one so these tests don't make real Groq calls or
depend on network access — they're purely testing the backfill control flow.
"""
import asyncio
from app.models.schemas import PaperInsights, RankedPaper
from app.services import extraction


def _make_paper(arxiv_id: str) -> RankedPaper:
    return RankedPaper(
        arxiv_id=arxiv_id,
        title=f"Paper {arxiv_id}",
        abstract="An abstract.",
        cross_encoder_score=0.5,
    )


def _success_insight(paper: RankedPaper) -> PaperInsights:
    return PaperInsights(
        arxiv_id=paper.arxiv_id, title=paper.title, problem="P", method="M"
    )


def _failed_insight(paper: RankedPaper) -> PaperInsights:
    return PaperInsights(
        arxiv_id=paper.arxiv_id,
        title=paper.title,
        problem=extraction._EXTRACTION_FAILED_MARKER,
        method=extraction._EXTRACTION_FAILED_MARKER,
    )


def test_all_succeed_returns_target_count(monkeypatch):
    papers = [_make_paper(str(i)) for i in range(5)]

    async def fake_extract_one(paper, semaphore):
        return _success_insight(paper)

    monkeypatch.setattr(extraction, "_extract_one", fake_extract_one)

    final_papers, insights = asyncio.run(
        extraction.extract_with_backfill(papers, target_count=3)
    )

    assert len(final_papers) == 3
    assert [p.arxiv_id for p in final_papers] == ["0", "1", "2"]
    assert len(insights) == 3


def test_failed_paper_is_dropped_and_backfilled(monkeypatch):
    papers = [_make_paper(str(i)) for i in range(5)]
    # Paper "1" always fails; everything else succeeds.
    failing_ids = {"1"}

    async def fake_extract_one(paper, semaphore):
        if paper.arxiv_id in failing_ids:
            return _failed_insight(paper)
        return _success_insight(paper)

    monkeypatch.setattr(extraction, "_extract_one", fake_extract_one)

    final_papers, insights = asyncio.run(
        extraction.extract_with_backfill(papers, target_count=3)
    )

    final_ids = [p.arxiv_id for p in final_papers]
    assert "1" not in final_ids  # the failing paper never appears
    assert len(final_ids) == 3   # still hit target_count via backfill
    # Backfilled from paper "3" (next in pool after primary batch [0,1,2]).
    assert final_ids == ["0", "2", "3"]


def test_failed_paper_is_never_retried(monkeypatch):
    """If a paper fails once, extract_with_backfill must not call it again."""
    papers = [_make_paper(str(i)) for i in range(4)]
    call_count: dict[str, int] = {}

    async def fake_extract_one(paper, semaphore):
        call_count[paper.arxiv_id] = call_count.get(paper.arxiv_id, 0) + 1
        if paper.arxiv_id == "0":
            return _failed_insight(paper)
        return _success_insight(paper)

    monkeypatch.setattr(extraction, "_extract_one", fake_extract_one)

    asyncio.run(extraction.extract_with_backfill(papers, target_count=3))

    assert call_count["0"] == 1  # called exactly once despite failing


def test_pool_exhausted_returns_fewer_than_target(monkeypatch):
    """If every paper fails, we should get back an empty result, not crash."""
    papers = [_make_paper(str(i)) for i in range(3)]

    async def fake_extract_one(paper, semaphore):
        return _failed_insight(paper)

    monkeypatch.setattr(extraction, "_extract_one", fake_extract_one)

    final_papers, insights = asyncio.run(
        extraction.extract_with_backfill(papers, target_count=5)
    )

    assert final_papers == []
    assert insights == []


def test_empty_input_returns_empty_output():
    final_papers, insights = asyncio.run(
        extraction.extract_with_backfill([], target_count=5)
    )
    assert final_papers == []
    assert insights == []

from datetime import datetime, timezone
from app.models.schemas import RankedPaper
from app.services import reranker


def _make_ranked_paper(arxiv_id: str, llm_score: float, published: str | None = None) -> RankedPaper:
    return RankedPaper(
        arxiv_id=arxiv_id,
        title=f"Paper {arxiv_id}",
        abstract="abstract",
        cross_encoder_score=0.5,
        llm_relevance_score=llm_score,
        published=published,
    )


def test_normalize_handles_equal_values():
    # All-equal input shouldn't divide by zero; should return a flat midpoint.
    assert reranker._normalize([5.0, 5.0, 5.0]) == [0.5, 0.5, 0.5]


def test_normalize_scales_to_0_1():
    result = reranker._normalize([0.0, 5.0, 10.0])
    assert result == [0.0, 0.5, 1.0]


def test_normalize_empty_list():
    assert reranker._normalize([]) == []


def test_recency_score_missing_date_is_zero():
    assert reranker._recency_score(None) == 0.0


def test_recency_score_current_year_is_high():
    current_year = datetime.now(timezone.utc).year
    assert reranker._recency_score(f"{current_year}-01-01") == 1.0


def test_recency_score_decreases_with_age():
    current_year = datetime.now(timezone.utc).year
    recent = reranker._recency_score(f"{current_year}-01-01")
    old = reranker._recency_score(f"{current_year - 5}-01-01")
    very_old = reranker._recency_score(f"{current_year - 20}-01-01")
    assert recent > old > very_old
    assert very_old == 0.0  # floors at 0, doesn't go negative


def test_recency_score_malformed_date_is_zero():
    assert reranker._recency_score("not-a-date") == 0.0


def test_blend_final_scores_assigns_citation_count(monkeypatch):
    papers = [_make_ranked_paper("a", llm_score=80), _make_ranked_paper("b", llm_score=40)]

    monkeypatch.setattr(
        reranker, "fetch_citation_counts", lambda ids: {"a": 100, "b": 0}
    )

    blended = reranker.blend_final_scores(papers)
    by_id = {p.arxiv_id: p for p in blended}

    assert by_id["a"].citation_count == 100
    assert by_id["b"].citation_count == 0
    assert all(p.final_score is not None for p in blended)


def test_blend_final_scores_sorts_by_final_score_descending(monkeypatch):
    papers = [
        _make_ranked_paper("low", llm_score=10),
        _make_ranked_paper("high", llm_score=90),
    ]
    monkeypatch.setattr(reranker, "fetch_citation_counts", lambda ids: {})

    blended = reranker.blend_final_scores(papers)
    assert blended[0].arxiv_id == "high"
    assert blended[1].arxiv_id == "low"


def test_blend_final_scores_empty_input():
    assert reranker.blend_final_scores([]) == []

from app.models.schemas import PipelineResult, ResearchGaps, ResearchMap
from app.services import history


def _make_result(topic: str) -> PipelineResult:
    return PipelineResult(
        topic=topic,
        candidates_found=10,
        ranked_papers=[],
        insights=[],
        research_map=ResearchMap(
            topic=topic, clusters=[], nodes=[], edges=[], open_problems=[], overview="x"
        ),
        research_gaps=ResearchGaps(future_work=["idea"]),
    )


def test_save_and_get_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "DB_PATH", tmp_path / "test_history.db")

    result = _make_result("test topic")
    run_id = history.save_run("test topic", result)

    fetched = history.get_run(run_id)
    assert fetched is not None
    assert fetched.topic == "test topic"
    assert fetched.research_gaps.future_work == ["idea"]


def test_get_nonexistent_run_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "DB_PATH", tmp_path / "test_history.db")
    assert history.get_run(99999) is None


def test_list_runs_orders_most_recent_first(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "DB_PATH", tmp_path / "test_history.db")

    history.save_run("first topic", _make_result("first topic"))
    history.save_run("second topic", _make_result("second topic"))

    runs = history.list_runs()
    assert runs[0]["topic"] == "second topic"
    assert runs[1]["topic"] == "first topic"


def test_list_runs_respects_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "DB_PATH", tmp_path / "test_history.db")

    for i in range(5):
        history.save_run(f"topic {i}", _make_result(f"topic {i}"))

    runs = history.list_runs(limit=2)
    assert len(runs) == 2

"""
Search history — persists each completed research run to SQLite so users
can revisit a past topic's results without re-running the full pipeline.

Deliberately simple: one table, JSON blob for the full result. This app is
single-user/local-first right now, so there's no need for a heavier
DB/migration setup — swap for Postgres if this ever needs multi-user access.
"""
import os
import sqlite3
import time
from pathlib import Path
from app.models.schemas import PipelineResult

# Configurable so the Docker volume can mount a dedicated data directory;
# defaults to the project root for local (non-Docker) development.
_default_path = Path(__file__).resolve().parent.parent.parent / "research_history.db"
DB_PATH = Path(os.environ.get("HISTORY_DB_PATH", str(_default_path)))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS research_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            created_at REAL NOT NULL,
            result_json TEXT NOT NULL
        )
        """
    )
    return conn


def save_run(topic: str, result: PipelineResult) -> int:
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO research_runs (topic, created_at, result_json) VALUES (?, ?, ?)",
        (topic, time.time(), result.model_dump_json()),
    )
    conn.commit()
    run_id = cur.lastrowid
    conn.close()
    return run_id


def list_runs(limit: int = 20) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, topic, created_at FROM research_runs ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [{"id": r[0], "topic": r[1], "created_at": r[2]} for r in rows]


def get_run(run_id: int) -> PipelineResult | None:
    conn = _get_conn()
    row = conn.execute(
        "SELECT result_json FROM research_runs WHERE id = ?", (run_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return PipelineResult.model_validate_json(row[0])

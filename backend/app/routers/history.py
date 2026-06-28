from fastapi import APIRouter, HTTPException
from app.models.schemas import HistoryEntry, PipelineResult
from app.services import history

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("", response_model=list[HistoryEntry])
def list_history(limit: int = 20):
    return history.list_runs(limit)


@router.get("/{run_id}", response_model=PipelineResult)
def get_history(run_id: int):
    result = history.get_run(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return result

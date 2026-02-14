from __future__ import annotations

from fastapi import APIRouter, Request

from text_to_sql.models.responses import HistoryResponse

router = APIRouter()


@router.get("/history", response_model=HistoryResponse)
async def query_history(
    request: Request,
    limit: int = 50,
    offset: int = 0,
) -> HistoryResponse:
    """Get paginated query history."""
    store = request.app.state.query_store
    records = await store.list(limit=limit, offset=offset)
    total = await store.count()
    return HistoryResponse(
        queries=[r.model_dump(mode="json") for r in records],
        total=total,
    )

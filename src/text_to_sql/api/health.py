from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    uptime_seconds: float
    metrics: dict[str, Any]


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    """Health check with pipeline metrics."""
    metrics = getattr(request.app.state, "metrics", None)
    if metrics:
        stats = await metrics.get_stats()
        uptime = stats.pop("uptime_seconds", 0.0)
    else:
        stats = {}
        uptime = 0.0

    return HealthResponse(
        status="ok",
        uptime_seconds=uptime,
        metrics=stats,
    )

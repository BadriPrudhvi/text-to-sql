from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()


class CacheStatsResponse(BaseModel):
    entries: int
    hits: int
    misses: int


class CacheFlushResponse(BaseModel):
    message: str


@router.get("/cache/stats", response_model=CacheStatsResponse)
async def cache_stats(request: Request) -> CacheStatsResponse:
    """Get cache hit/miss statistics."""
    cache = request.app.state.orchestrator.query_cache
    if cache is None:
        raise HTTPException(status_code=501, detail="Cache not configured")
    stats = await cache.stats()
    return CacheStatsResponse(**stats)


@router.post("/cache/flush", response_model=CacheFlushResponse)
async def flush_cache(request: Request) -> CacheFlushResponse:
    """Flush all cached queries."""
    rate_limiter = request.app.state.rate_limiter
    if rate_limiter and not rate_limiter.check(request.client.host if request.client else "unknown"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    cache = request.app.state.orchestrator.query_cache
    if cache is None:
        raise HTTPException(status_code=501, detail="Cache not configured")
    await cache.invalidate_all()
    return CacheFlushResponse(message="Cache flushed successfully")

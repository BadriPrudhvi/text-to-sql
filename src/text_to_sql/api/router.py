from __future__ import annotations

from fastapi import APIRouter

from text_to_sql.api.approve import router as approve_router
from text_to_sql.api.cache import router as cache_router
from text_to_sql.api.conversation import router as conversation_router
from text_to_sql.api.health import router as health_router
from text_to_sql.api.history import router as history_router
from text_to_sql.api.query import router as query_router

api_router = APIRouter()
api_router.include_router(query_router, tags=["query"])
api_router.include_router(approve_router, tags=["approval"])
api_router.include_router(history_router, tags=["history"])
api_router.include_router(conversation_router, tags=["conversations"])
api_router.include_router(cache_router, tags=["cache"])
api_router.include_router(health_router, tags=["health"])

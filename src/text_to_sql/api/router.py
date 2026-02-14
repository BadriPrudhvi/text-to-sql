from __future__ import annotations

from fastapi import APIRouter

from text_to_sql.api.approve import router as approve_router
from text_to_sql.api.history import router as history_router
from text_to_sql.api.query import router as query_router

api_router = APIRouter()
api_router.include_router(query_router, tags=["query"])
api_router.include_router(approve_router, tags=["approval"])
api_router.include_router(history_router, tags=["history"])

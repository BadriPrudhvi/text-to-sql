from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from text_to_sql.models.responses import QueryResponse, status_message

router = APIRouter()


class CreateSessionResponse(BaseModel):
    session_id: str


class SessionQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


class SessionHistoryResponse(BaseModel):
    session_id: str
    queries: list[dict]
    total: int


@router.post("/conversations", response_model=CreateSessionResponse)
async def create_session(request: Request) -> CreateSessionResponse:
    """Create a new conversation session."""
    session_store = request.app.state.orchestrator.session_store
    if session_store is None:
        raise HTTPException(status_code=501, detail="Session store not configured")
    session = await session_store.create()
    return CreateSessionResponse(session_id=session.id)


@router.post("/conversations/{session_id}/query", response_model=QueryResponse)
async def submit_session_query(
    session_id: str, body: SessionQueryRequest, request: Request
) -> QueryResponse:
    """Submit a question within a conversation session (non-streaming)."""
    rate_limiter = request.app.state.rate_limiter
    client_ip = request.client.host if request.client else "unknown"
    if not rate_limiter.check(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    orchestrator = request.app.state.orchestrator
    if orchestrator.session_store is None:
        raise HTTPException(status_code=501, detail="Session store not configured")

    try:
        await orchestrator.session_store.get(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    record = await orchestrator.submit_question_in_session(body.question, session_id)
    return QueryResponse(
        query_id=record.id,
        question=record.natural_language,
        generated_sql=record.generated_sql,
        validation_errors=record.validation_errors,
        approval_status=record.approval_status,
        message=status_message(record.approval_status),
        result=record.result,
        answer=record.answer,
        error=record.error,
    )


@router.get("/conversations/{session_id}/stream")
async def stream_session_query(
    session_id: str,
    request: Request,
    question: str = Query(..., min_length=1, max_length=2000),
) -> EventSourceResponse:
    """Stream pipeline events for a question via SSE."""
    rate_limiter = request.app.state.rate_limiter
    client_ip = request.client.host if request.client else "unknown"
    if not rate_limiter.check(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    orchestrator = request.app.state.orchestrator
    if orchestrator.session_store is None:
        raise HTTPException(status_code=501, detail="Session store not configured")

    try:
        await orchestrator.session_store.get(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    async def event_generator():
        async for event in orchestrator.stream_question(question, session_id):
            event_type = event.get("event", "update") if isinstance(event, dict) else "update"
            yield {"event": event_type, "data": json.dumps(event)}
        yield {"event": "done", "data": "{}"}

    return EventSourceResponse(event_generator())


@router.get("/conversations/{session_id}/history", response_model=SessionHistoryResponse)
async def get_session_history(
    session_id: str,
    request: Request,
) -> SessionHistoryResponse:
    """Get all queries in a conversation session."""
    orchestrator = request.app.state.orchestrator
    if orchestrator.session_store is None:
        raise HTTPException(status_code=501, detail="Session store not configured")

    try:
        session = await orchestrator.session_store.get(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    queries = []
    for query_id in session.query_ids:
        try:
            record = await orchestrator.query_store.get(query_id)
            queries.append(record.model_dump(mode="json"))
        except KeyError:
            continue

    return SessionHistoryResponse(
        session_id=session_id,
        queries=queries,
        total=len(queries),
    )

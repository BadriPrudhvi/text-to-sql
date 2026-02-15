from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from text_to_sql.models.requests import QueryRequest
from text_to_sql.models.responses import QueryResponse, status_message

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def submit_query(body: QueryRequest, request: Request) -> QueryResponse:
    """Submit a natural language question to generate SQL.

    Valid queries are auto-executed. Queries with validation errors pause for human review.
    """
    rate_limiter = getattr(request.app.state, "rate_limiter", None)
    if rate_limiter:
        client_ip = request.client.host if request.client else "unknown"
        if not rate_limiter.check(client_ip):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

    orchestrator = request.app.state.orchestrator
    metrics = getattr(request.app.state, "metrics", None)

    if metrics:
        await metrics.increment("queries_total")

    record = await orchestrator.submit_question(body.question)

    if metrics:
        if record.approval_status.value == "executed":
            await metrics.increment("queries_executed")
        elif record.approval_status.value == "failed":
            await metrics.increment("queries_failed")

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
        query_type=record.query_type,
        analysis_plan=record.analysis_plan,
        analysis_steps=record.analysis_steps,
    )

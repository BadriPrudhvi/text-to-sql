from __future__ import annotations

from fastapi import APIRouter, Request

from text_to_sql.models.requests import QueryRequest
from text_to_sql.models.responses import QueryResponse, status_message

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def submit_query(body: QueryRequest, request: Request) -> QueryResponse:
    """Submit a natural language question to generate SQL.

    Valid queries are auto-executed. Queries with validation errors pause for human review.
    """
    orchestrator = request.app.state.orchestrator
    record = await orchestrator.submit_question(body.question)
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

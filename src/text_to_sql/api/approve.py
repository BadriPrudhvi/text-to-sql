from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from text_to_sql.models.requests import ApprovalRequest
from text_to_sql.models.responses import ApprovalResponse

router = APIRouter()


@router.post("/approve/{query_id}", response_model=ApprovalResponse)
async def approve_query(
    query_id: str, body: ApprovalRequest, request: Request
) -> ApprovalResponse:
    """Approve or reject a pending SQL query. Approved queries are auto-executed."""
    orchestrator = request.app.state.orchestrator
    try:
        if body.approved:
            await orchestrator.approval_manager.approve(
                query_id, modified_sql=body.modified_sql
            )
            record = await orchestrator.execute_approved(query_id)
        else:
            record = await orchestrator.approval_manager.reject(query_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Query {query_id} not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ApprovalResponse(
        query_id=record.id,
        approval_status=record.approval_status,
        result=record.result,
        answer=record.answer,
        error=record.error,
    )

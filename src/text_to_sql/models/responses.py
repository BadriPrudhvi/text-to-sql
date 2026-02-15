from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from text_to_sql.models.domain import ApprovalStatus


def status_message(status: ApprovalStatus) -> str:
    """Human-readable message for a given approval status."""
    if status == ApprovalStatus.EXECUTED:
        return "Query executed successfully."
    if status == ApprovalStatus.FAILED:
        return "Query execution failed."
    return "SQL generated. Awaiting approval."


class QueryResponse(BaseModel):
    query_id: str
    question: str
    generated_sql: str
    validation_errors: list[str] = Field(default_factory=list)
    approval_status: ApprovalStatus
    message: str = ""
    result: list[dict[str, Any]] | None = None
    error: str | None = None


class ApprovalResponse(BaseModel):
    query_id: str
    approval_status: ApprovalStatus
    result: list[dict[str, Any]] | None = None
    error: str | None = None


class HistoryResponse(BaseModel):
    queries: list[dict[str, Any]]
    total: int

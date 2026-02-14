from __future__ import annotations

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(
        ..., min_length=1, max_length=2000, description="Natural language question"
    )


class ApprovalRequest(BaseModel):
    approved: bool
    modified_sql: str | None = Field(
        default=None, description="Optionally edit SQL before approval"
    )

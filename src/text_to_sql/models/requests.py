from __future__ import annotations

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(
        ..., min_length=1, max_length=2000, description="Natural language question"
    )
    database: str = Field(default="primary", description="Database alias to query against")


class ApprovalRequest(BaseModel):
    approved: bool
    modified_sql: str | None = Field(
        default=None, description="Optionally edit SQL before approval"
    )

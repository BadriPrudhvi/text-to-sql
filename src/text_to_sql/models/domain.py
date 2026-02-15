from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    FAILED = "failed"


class ColumnInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    data_type: str
    is_nullable: bool = True
    description: str = ""


class TableInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    catalog: str = ""
    schema_name: str = ""
    table_name: str
    table_type: str = "TABLE"
    description: str = ""
    columns: list[ColumnInfo] = Field(default_factory=list)


class SchemaInfo(BaseModel):
    tables: list[TableInfo] = Field(default_factory=list)
    discovered_at: datetime = Field(default_factory=_utcnow)


class SessionInfo(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=_utcnow)
    last_activity: datetime = Field(default_factory=_utcnow)
    query_ids: list[str] = Field(default_factory=list)


class QueryRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str | None = None
    natural_language: str
    database_type: str
    generated_sql: str = ""
    validation_errors: list[str] = Field(default_factory=list)
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    result: list[dict[str, Any]] | None = None
    answer: str | None = None
    error: str | None = None
    query_type: str = "simple"
    analysis_plan: list[dict[str, str]] | None = None
    analysis_steps: list[dict[str, Any]] | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    approved_at: datetime | None = None
    executed_at: datetime | None = None

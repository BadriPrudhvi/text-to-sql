from __future__ import annotations

from datetime import datetime, timezone

from text_to_sql.db.base import check_read_only
from text_to_sql.models.domain import ApprovalStatus, QueryRecord
from text_to_sql.store.base import QueryStore


class ApprovalManager:
    """Manages the human-in-the-loop approval lifecycle."""

    def __init__(self, query_store: QueryStore) -> None:
        self._store = query_store

    async def submit_for_approval(self, record: QueryRecord) -> QueryRecord:
        """Store a query record and set status to PENDING."""
        record.approval_status = ApprovalStatus.PENDING
        await self._store.save(record)
        return record

    async def approve(self, query_id: str, modified_sql: str | None = None) -> QueryRecord:
        """Approve a pending query, optionally with modified SQL."""
        record = await self._store.get(query_id)
        if record.approval_status != ApprovalStatus.PENDING:
            raise ValueError(
                f"Query {query_id} is not pending approval "
                f"(current status: {record.approval_status.value})"
            )
        if modified_sql:
            errors = check_read_only(modified_sql)
            if errors:
                raise ValueError(f"Modified SQL rejected: {errors[0]}")
            record.generated_sql = modified_sql
        record.approval_status = ApprovalStatus.APPROVED
        record.approved_at = datetime.now(timezone.utc)
        await self._store.save(record)
        return record

    async def reject(self, query_id: str) -> QueryRecord:
        """Reject a pending query."""
        record = await self._store.get(query_id)
        if record.approval_status != ApprovalStatus.PENDING:
            raise ValueError(
                f"Query {query_id} is not pending approval "
                f"(current status: {record.approval_status.value})"
            )
        record.approval_status = ApprovalStatus.REJECTED
        await self._store.save(record)
        return record

from __future__ import annotations

import asyncio

from text_to_sql.models.domain import QueryRecord


class InMemoryQueryStore:
    """In-memory query record store for development and MVP use."""

    def __init__(self) -> None:
        self._records: dict[str, QueryRecord] = {}
        self._lock = asyncio.Lock()

    async def save(self, record: QueryRecord) -> None:
        async with self._lock:
            self._records[record.id] = record

    async def get(self, query_id: str) -> QueryRecord:
        record = self._records.get(query_id)
        if not record:
            raise KeyError(f"Query {query_id} not found")
        return record

    async def list(self, limit: int = 50, offset: int = 0) -> list[QueryRecord]:
        all_records = sorted(
            self._records.values(),
            key=lambda r: r.created_at,
            reverse=True,
        )
        return all_records[offset : offset + limit]

    async def count(self) -> int:
        return len(self._records)

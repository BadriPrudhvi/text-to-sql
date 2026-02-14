from __future__ import annotations

from typing import Protocol

from text_to_sql.models.domain import QueryRecord


class QueryStore(Protocol):
    """Protocol for query record persistence."""

    async def save(self, record: QueryRecord) -> None: ...

    async def get(self, query_id: str) -> QueryRecord: ...

    async def list(self, limit: int = 50, offset: int = 0) -> list[QueryRecord]: ...

    async def count(self) -> int: ...

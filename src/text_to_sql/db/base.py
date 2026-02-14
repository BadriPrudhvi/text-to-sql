from __future__ import annotations

from typing import Any, Protocol

from text_to_sql.models.domain import TableInfo


class DatabaseBackend(Protocol):
    """Protocol for all database backends."""

    async def connect(self) -> None: ...

    async def close(self) -> None: ...

    async def discover_tables(self) -> list[TableInfo]: ...

    async def validate_sql(self, sql: str) -> list[str]:
        """Validate SQL syntax. Returns list of error strings (empty = valid)."""
        ...

    async def execute_sql(self, sql: str) -> list[dict[str, Any]]:
        """Execute a read-only SQL query and return rows as dicts."""
        ...

    @property
    def backend_type(self) -> str: ...


_FORBIDDEN_KEYWORDS = frozenset(
    {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE", "GRANT", "REVOKE"}
)


def check_read_only(sql: str) -> list[str]:
    """Check that SQL does not contain DML/DDL keywords. Returns errors."""
    words = sql.upper().split()
    first_word = words[0] if words else ""
    if first_word in _FORBIDDEN_KEYWORDS:
        return [f"Forbidden SQL operation: {first_word}. Only SELECT/WITH queries are allowed."]
    return []

from __future__ import annotations

import re
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

_SQL_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_SQL_LINE_COMMENT_RE = re.compile(r"--.*?(\n|$)")


def check_read_only(sql: str) -> list[str]:
    """Check that SQL is a safe read-only query. Returns list of errors."""
    # Strip SQL comments that could hide forbidden keywords
    normalized = _SQL_COMMENT_RE.sub(" ", sql)
    normalized = _SQL_LINE_COMMENT_RE.sub(" ", normalized)
    normalized = normalized.strip()

    if not normalized:
        return ["Empty SQL query"]

    # Block multiple statements
    stripped = normalized.rstrip(";").strip()
    if ";" in stripped:
        return ["Multiple SQL statements are not allowed"]

    # Check all tokens for forbidden keywords (not just the first word)
    words = normalized.upper().split()
    for word in words:
        if word in _FORBIDDEN_KEYWORDS:
            return [f"Forbidden SQL operation: {word}. Only SELECT/WITH queries are allowed."]

    # Only allow queries starting with SELECT or WITH
    first_word = words[0] if words else ""
    if first_word not in {"SELECT", "WITH", "EXPLAIN"}:
        return [f"Only SELECT/WITH queries are allowed, got: {first_word}"]

    return []


_SAFE_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def validate_identifier(name: str) -> bool:
    """Check that a SQL identifier (table/column name) is safe."""
    return bool(_SAFE_IDENTIFIER_RE.match(name))

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

    async def execute_sql(
        self, sql: str, timeout_seconds: float | None = None
    ) -> list[dict[str, Any]]:
        """Execute a read-only SQL query and return rows as dicts."""
        ...

    @property
    def backend_type(self) -> str: ...


_FORBIDDEN_KEYWORDS = frozenset(
    {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE", "GRANT", "REVOKE"}
)

_DIALECT_FORBIDDEN: dict[str, frozenset[str]] = {
    "postgres": frozenset({"MERGE", "COPY", "CALL", "EXECUTE", "DO", "LISTEN", "NOTIFY"}),
    "bigquery": frozenset({"MERGE", "EXPORT", "LOAD", "CALL", "ASSERT"}),
    "sqlite": frozenset({"ATTACH", "DETACH", "REPLACE", "REINDEX"}),
}

_SQL_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_SQL_LINE_COMMENT_RE = re.compile(r"--.*?(\n|$)")


def check_read_only(sql: str, *, dialect: str | None = None) -> list[str]:
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

    # Combine base + dialect-specific forbidden keywords
    forbidden = _FORBIDDEN_KEYWORDS
    if dialect and dialect in _DIALECT_FORBIDDEN:
        forbidden = _FORBIDDEN_KEYWORDS | _DIALECT_FORBIDDEN[dialect]

    # Check all tokens for forbidden keywords (not just the first word)
    words = normalized.upper().split()
    for word in words:
        if word in forbidden:
            return [f"Forbidden SQL operation: {word}. Only SELECT/WITH queries are allowed."]

    # Only allow queries starting with SELECT or WITH
    first_word = words[0] if words else ""
    if first_word not in {"SELECT", "WITH", "EXPLAIN"}:
        return [f"Only SELECT/WITH queries are allowed, got: {first_word}"]

    # Block system catalog / schema exploration queries — the schema is
    # already provided in the prompt, so the LLM should not discover it.
    upper = normalized.upper()
    if any(cat in upper for cat in ("SQLITE_MASTER", "SQLITE_SCHEMA", "SQLITE_TEMP_MASTER")):
        return ["Do not query system catalogs (sqlite_master). Use the schema provided in the prompt."]
    if "INFORMATION_SCHEMA" in upper:
        return ["Do not query information_schema. Use the schema provided in the prompt."]

    return []


def clean_llm_sql(sql: str) -> str:
    """Strip trailing explanatory text that LLMs sometimes append after SQL."""
    # Strip markdown code fences
    if sql.startswith("```"):
        lines = sql.split("\n")
        sql = "\n".join(line for line in lines if not line.startswith("```")).strip()
    # If semicolon present, take everything up to the last one
    last_semi = sql.rfind(";")
    if last_semi != -1:
        return sql[: last_semi].strip()
    # No semicolon — split on blank line (LLMs put blank line before explanation)
    parts = sql.split("\n\n")
    if len(parts) > 1:
        return parts[0].strip()
    return sql.strip()


_SAFE_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

_POSTGRES_IDENTIFIER_RE = re.compile(
    r'^("([^"]+)"'                    # quoted identifier
    r'|[a-zA-Z_$][a-zA-Z0-9_$]*)'    # unquoted (allows $)
    r'(\.'                            # optional .schema
    r'("([^"]+)"'
    r'|[a-zA-Z_$][a-zA-Z0-9_$]*))*$'
)
_BIGQUERY_IDENTIFIER_RE = re.compile(
    r'^(`[a-zA-Z0-9_][a-zA-Z0-9_.:-]*`'  # backtick-quoted (allows hyphens, dots, colons)
    r'|[a-zA-Z_][a-zA-Z0-9_]*'           # unquoted simple
    r'(\.[a-zA-Z_][a-zA-Z0-9_]*)*)$'     # optional dot-separated parts
)


def validate_identifier(name: str, dialect: str | None = None) -> bool:
    """Check that a SQL identifier (table/column name) is safe for the given dialect."""
    if dialect == "postgres":
        return bool(_POSTGRES_IDENTIFIER_RE.match(name))
    if dialect == "bigquery":
        return bool(_BIGQUERY_IDENTIFIER_RE.match(name))
    return bool(_SAFE_IDENTIFIER_RE.match(name))

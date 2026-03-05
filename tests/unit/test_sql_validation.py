"""Tests for SQL validation edge cases."""

from __future__ import annotations

import pytest

from text_to_sql.db.base import check_read_only, clean_llm_sql, validate_identifier
from text_to_sql.db.sqlite import SqliteBackend


class TestCheckReadOnly:
    """Tests for check_read_only guard."""

    def test_simple_select(self) -> None:
        assert check_read_only("SELECT * FROM users") == []

    def test_select_with_trailing_semicolon(self) -> None:
        assert check_read_only("SELECT 1;") == []

    def test_multiple_statements_rejected(self) -> None:
        errors = check_read_only("SELECT 1; DROP TABLE users")
        assert len(errors) == 1
        assert "Multiple SQL statements" in errors[0]

    def test_with_cte(self) -> None:
        sql = "WITH cte AS (SELECT 1) SELECT * FROM cte"
        assert check_read_only(sql) == []

    def test_forbidden_keyword_rejected(self) -> None:
        errors = check_read_only("DROP TABLE users")
        assert len(errors) == 1
        assert "Forbidden" in errors[0]

    def test_empty_query_rejected(self) -> None:
        errors = check_read_only("")
        assert len(errors) == 1
        assert "Empty" in errors[0]


class TestCleanLlmSql:
    """Tests for clean_llm_sql utility."""

    def test_clean_sql_passes_through(self) -> None:
        sql = "SELECT * FROM users WHERE id = 1"
        assert clean_llm_sql(sql) == sql

    def test_strips_trailing_explanation_after_semicolon(self) -> None:
        raw = "SELECT * FROM users;\nThis query retrieves all users from the table."
        assert clean_llm_sql(raw) == "SELECT * FROM users"

    def test_strips_trailing_explanation_after_blank_line(self) -> None:
        raw = "SELECT * FROM users\n\nThis query retrieves all users from the table."
        assert clean_llm_sql(raw) == "SELECT * FROM users"

    def test_strips_markdown_code_fences(self) -> None:
        raw = "```sql\nSELECT * FROM users;\n```"
        assert clean_llm_sql(raw) == "SELECT * FROM users"

    def test_strips_markdown_fences_with_explanation(self) -> None:
        raw = "```sql\nSELECT * FROM users;\n```\nThis returns all users."
        assert clean_llm_sql(raw) == "SELECT * FROM users"

    def test_no_semicolon_no_blank_line_passes_through(self) -> None:
        sql = "SELECT count(*) FROM orders"
        assert clean_llm_sql(sql) == sql

    def test_multiline_sql_with_semicolon(self) -> None:
        raw = "SELECT\n  id,\n  name\nFROM users\nWHERE active = 1;"
        assert clean_llm_sql(raw) == "SELECT\n  id,\n  name\nFROM users\nWHERE active = 1"


class TestDialectReadOnly:
    """Tests for dialect-aware check_read_only guard."""

    # --- PostgreSQL dialect ---
    @pytest.mark.parametrize("keyword", ["MERGE", "COPY", "CALL", "EXECUTE", "DO", "LISTEN", "NOTIFY"])
    def test_postgres_rejects_dialect_keywords(self, keyword: str) -> None:
        errors = check_read_only(f"{keyword} something", dialect="postgres")
        assert len(errors) == 1
        assert "Forbidden" in errors[0] or "Only SELECT" in errors[0]

    def test_postgres_allows_select(self) -> None:
        assert check_read_only("SELECT 1", dialect="postgres") == []

    # --- BigQuery dialect ---
    @pytest.mark.parametrize("keyword", ["MERGE", "EXPORT", "LOAD", "CALL", "ASSERT"])
    def test_bigquery_rejects_dialect_keywords(self, keyword: str) -> None:
        errors = check_read_only(f"{keyword} something", dialect="bigquery")
        assert len(errors) == 1
        assert "Forbidden" in errors[0] or "Only SELECT" in errors[0]

    def test_bigquery_allows_select(self) -> None:
        assert check_read_only("SELECT 1", dialect="bigquery") == []

    # --- SQLite dialect ---
    @pytest.mark.parametrize("keyword", ["ATTACH", "DETACH", "REPLACE", "REINDEX"])
    def test_sqlite_rejects_dialect_keywords(self, keyword: str) -> None:
        errors = check_read_only(f"{keyword} something", dialect="sqlite")
        assert len(errors) == 1
        assert "Forbidden" in errors[0] or "Only SELECT" in errors[0]

    def test_sqlite_allows_select(self) -> None:
        assert check_read_only("SELECT 1", dialect="sqlite") == []

    # --- No dialect (default) uses base keywords only ---
    def test_no_dialect_allows_dialect_specific_keywords(self) -> None:
        """Without dialect, dialect-specific keywords are not blocked (caught by first-word check only)."""
        # MERGE is not in base forbidden set, but will fail the first-word check
        errors = check_read_only("SELECT MERGE FROM t")
        assert errors == []  # MERGE as a column name in SELECT is fine

    def test_no_dialect_still_blocks_base_keywords(self) -> None:
        errors = check_read_only("DROP TABLE users")
        assert len(errors) == 1
        assert "Forbidden" in errors[0]

    # --- Comment injection ---
    def test_comment_with_hidden_merge_in_select_passes(self) -> None:
        """SELECT with MERGE hidden inside a comment should pass for postgres dialect."""
        sql = "SELECT /* hidden MERGE */ 1"
        assert check_read_only(sql, dialect="postgres") == []

    def test_comment_injection_merge_stripped_passes(self) -> None:
        """Block-comment wrapping MERGE — once stripped, it's just SELECT 1."""
        sql = "/* MERGE */ SELECT 1"
        assert check_read_only(sql, dialect="postgres") == []


class TestSqliteValidateSql:
    """Tests for SqliteBackend.validate_sql with special characters."""

    @pytest.fixture
    async def backend(self) -> SqliteBackend:
        db = SqliteBackend("sqlite+aiosqlite://")
        await db.connect()
        yield db  # type: ignore[misc]
        await db.close()

    @pytest.mark.asyncio
    async def test_dollar_sign_in_string_literal(self, backend: SqliteBackend) -> None:
        """SQL with $ in string literals should not cause KeyError."""
        sql = "SELECT * FROM sqlite_master WHERE name = '$test'"
        errors = await backend.validate_sql(sql)
        assert errors == []

    @pytest.mark.asyncio
    async def test_colon_in_string_literal(self, backend: SqliteBackend) -> None:
        """SQL with :word in string literals should not cause bind param errors."""
        sql = "SELECT * FROM sqlite_master WHERE name = ':placeholder'"
        errors = await backend.validate_sql(sql)
        assert errors == []

    @pytest.mark.asyncio
    async def test_invalid_sql_returns_error(self, backend: SqliteBackend) -> None:
        """Invalid SQL should return validation errors, not raise."""
        sql = "SELECT * FROM nonexistent_table_xyz"
        errors = await backend.validate_sql(sql)
        assert len(errors) > 0

    @pytest.mark.asyncio
    async def test_valid_select(self, backend: SqliteBackend) -> None:
        sql = "SELECT 1 AS value"
        errors = await backend.validate_sql(sql)
        assert errors == []


class TestSqliteExecuteSql:
    """Tests for SqliteBackend.execute_sql with special characters."""

    @pytest.fixture
    async def backend(self) -> SqliteBackend:
        db = SqliteBackend("sqlite+aiosqlite://")
        await db.connect()
        try:
            yield db  # type: ignore[misc]
        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_dollar_sign_in_string_literal(self, backend: SqliteBackend) -> None:
        """execute_sql should handle $ in string literals without KeyError."""
        rows = await backend.execute_sql("SELECT '$100' AS price")
        assert rows == [{"price": "$100"}]

    @pytest.mark.asyncio
    async def test_colon_in_string_literal(self, backend: SqliteBackend) -> None:
        """execute_sql should handle :word in string literals without bind param errors."""
        rows = await backend.execute_sql("SELECT ':placeholder' AS val")
        assert rows == [{"val": ":placeholder"}]


class TestDialectIdentifierValidation:
    """Tests for dialect-aware validate_identifier."""

    # SQLite — strict (existing behavior)
    def test_sqlite_simple_name(self) -> None:
        assert validate_identifier("users", dialect="sqlite") is True

    def test_sqlite_rejects_hyphen(self) -> None:
        assert validate_identifier("my-table", dialect="sqlite") is False

    # PostgreSQL — allows schema.table and quoted identifiers
    def test_postgres_simple_name(self) -> None:
        assert validate_identifier("users", dialect="postgres") is True

    def test_postgres_qualified_name(self) -> None:
        assert validate_identifier("public.users", dialect="postgres") is True

    def test_postgres_quoted_identifier(self) -> None:
        assert validate_identifier('"Order Details"', dialect="postgres") is True

    def test_postgres_dollar_sign(self) -> None:
        assert validate_identifier("sys$users", dialect="postgres") is True

    def test_postgres_rejects_semicolon(self) -> None:
        assert validate_identifier("users;drop", dialect="postgres") is False

    # BigQuery — allows backticks, hyphens in project IDs
    def test_bigquery_simple_name(self) -> None:
        assert validate_identifier("users", dialect="bigquery") is True

    def test_bigquery_backtick_quoted(self) -> None:
        assert validate_identifier("`my-project.dataset.table`", dialect="bigquery") is True

    def test_bigquery_qualified_no_backticks(self) -> None:
        assert validate_identifier("dataset.table_name", dialect="bigquery") is True

    def test_bigquery_rejects_semicolon(self) -> None:
        assert validate_identifier("table;drop", dialect="bigquery") is False

    # Default (no dialect) — strict
    def test_default_simple(self) -> None:
        assert validate_identifier("users") is True

    def test_default_rejects_dot(self) -> None:
        assert validate_identifier("schema.table") is False

"""Tests for SQL validation edge cases."""

from __future__ import annotations

import pytest

from text_to_sql.db.base import check_read_only
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

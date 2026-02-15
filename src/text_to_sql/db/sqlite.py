from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from text_to_sql.db.base import check_read_only, validate_identifier
from text_to_sql.models.domain import ColumnInfo, TableInfo

logger = structlog.get_logger()


class SqliteBackend:
    """SQLite database backend using SQLAlchemy async + aiosqlite."""

    def __init__(self, url: str) -> None:
        self._url = url
        self._engine: AsyncEngine | None = None

    async def connect(self) -> None:
        self._engine = create_async_engine(self._url, echo=False)
        logger.info("sqlite_connected", url=self._url)

    async def close(self) -> None:
        if self._engine:
            await self._engine.dispose()

    async def discover_tables(self) -> list[TableInfo]:
        assert self._engine is not None

        async with self._engine.connect() as conn:
            # Get all user tables
            result = await conn.execute(
                text("SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%'")
            )
            table_rows = result.fetchall()

            tables: list[TableInfo] = []
            for table_row in table_rows:
                table_name = table_row[0]
                table_type = "VIEW" if table_row[1] == "view" else "TABLE"

                # Validate table name before interpolation into PRAGMA
                if not validate_identifier(table_name):
                    logger.warning("sqlite_invalid_table_name", table_name=table_name)
                    continue

                # Get column info via PRAGMA (doesn't support parameterized queries)
                col_result = await conn.execute(text(f"PRAGMA table_info('{table_name}')"))
                col_rows = col_result.fetchall()

                columns = [
                    ColumnInfo(
                        name=col[1],
                        data_type=col[2] or "TEXT",
                        is_nullable=col[3] == 0,  # notnull column
                    )
                    for col in col_rows
                ]
                tables.append(
                    TableInfo(
                        table_name=table_name,
                        table_type=table_type,
                        columns=columns,
                    )
                )

        logger.info("sqlite_schema_discovered", table_count=len(tables))
        return tables

    async def validate_sql(self, sql: str) -> list[str]:
        assert self._engine is not None
        errors = check_read_only(sql)
        if errors:
            return errors

        try:
            # check_read_only already verified the SQL is safe for EXPLAIN
            async with self._engine.connect() as conn:
                await conn.execute(text("EXPLAIN " + sql))
            return []
        except Exception as e:
            return [str(e)]

    async def execute_sql(self, sql: str) -> list[dict[str, Any]]:
        assert self._engine is not None
        errors = check_read_only(sql)
        if errors:
            raise ValueError(errors[0])

        async with self._engine.connect() as conn:
            result = await conn.execute(text(sql))
            rows = [dict(row._mapping) for row in result]

        logger.info("sqlite_query_executed", row_count=len(rows))
        return rows

    @property
    def backend_type(self) -> str:
        return "sqlite"

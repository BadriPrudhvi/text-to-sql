from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from text_to_sql.db.base import check_read_only
from text_to_sql.models.domain import ColumnInfo, TableInfo

logger = structlog.get_logger()


class PostgresBackend:
    """PostgreSQL database backend using SQLAlchemy async."""

    def __init__(self, url: str) -> None:
        self._url = url
        self._engine: AsyncEngine | None = None

    async def connect(self) -> None:
        self._engine = create_async_engine(self._url, echo=False)
        logger.info("postgres_connected", url=self._url.split("@")[-1])

    async def close(self) -> None:
        if self._engine:
            await self._engine.dispose()

    async def discover_tables(self) -> list[TableInfo]:
        assert self._engine is not None

        query = text("""
            SELECT
                t.table_schema,
                t.table_name,
                t.table_type,
                c.column_name,
                c.data_type,
                c.is_nullable,
                col_description(cls.oid, c.ordinal_position) AS column_description,
                obj_description(cls.oid) AS table_description
            FROM information_schema.columns c
            JOIN information_schema.tables t USING (table_schema, table_name)
            LEFT JOIN pg_catalog.pg_class cls
                ON cls.relname = t.table_name
                AND cls.relnamespace = (
                    SELECT oid FROM pg_catalog.pg_namespace WHERE nspname = t.table_schema
                )
            WHERE t.table_schema NOT IN ('information_schema', 'pg_catalog')
            ORDER BY t.table_schema, t.table_name, c.ordinal_position
        """)

        async with self._engine.connect() as conn:
            result = await conn.execute(query)
            rows = result.mappings().all()

        tables_map: dict[str, TableInfo] = {}
        for row in rows:
            key = f"{row['table_schema']}.{row['table_name']}"
            if key not in tables_map:
                tables_map[key] = TableInfo(
                    schema_name=row["table_schema"],
                    table_name=row["table_name"],
                    table_type=row["table_type"],
                    description=row.get("table_description") or "",
                    columns=[],
                )
            cols = list(tables_map[key].columns)
            cols.append(
                ColumnInfo(
                    name=row["column_name"],
                    data_type=row["data_type"],
                    is_nullable=row["is_nullable"] == "YES",
                    description=row.get("column_description") or "",
                )
            )
            tables_map[key] = tables_map[key].model_copy(update={"columns": cols})

        tables = list(tables_map.values())
        logger.info("postgres_schema_discovered", table_count=len(tables))
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

    async def execute_sql(
        self, sql: str, timeout_seconds: float | None = None
    ) -> list[dict[str, Any]]:
        assert self._engine is not None
        errors = check_read_only(sql)
        if errors:
            raise ValueError(errors[0])

        async with self._engine.connect() as conn:
            if timeout_seconds:
                timeout_ms = int(timeout_seconds * 1000)
                await conn.execute(text("SET statement_timeout = :timeout"), {"timeout": timeout_ms})
            result = await conn.execute(text(sql))
            rows = [dict(row._mapping) for row in result]

        logger.info("postgres_query_executed", row_count=len(rows))
        return rows

    @property
    def backend_type(self) -> str:
        return "postgres"

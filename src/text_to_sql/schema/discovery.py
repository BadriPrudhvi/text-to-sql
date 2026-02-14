from __future__ import annotations

import structlog

from text_to_sql.db.base import DatabaseBackend
from text_to_sql.models.domain import SchemaInfo, TableInfo
from text_to_sql.schema.cache import SchemaCache

logger = structlog.get_logger()


class SchemaDiscoveryService:
    """Discovers and caches database schema metadata."""

    def __init__(self, backend: DatabaseBackend, cache: SchemaCache) -> None:
        self._backend = backend
        self._cache = cache

    async def get_schema(self, force_refresh: bool = False) -> SchemaInfo:
        cache_key = self._backend.backend_type
        if not force_refresh:
            cached = await self._cache.get(cache_key)
            if cached:
                logger.debug("schema_cache_hit", backend=cache_key)
                return cached

        tables = await self._backend.discover_tables()
        schema = SchemaInfo(tables=tables)
        await self._cache.set(cache_key, schema)
        logger.info("schema_discovered", backend=cache_key, table_count=len(tables))
        return schema

    def schema_to_prompt_context(self, schema: SchemaInfo) -> str:
        """Format schema metadata as CREATE TABLE DDL for LLM context."""
        parts: list[str] = []
        for table in schema.tables:
            qualified = self._qualify_table_name(table)
            col_defs = []
            for col in table.columns:
                nullable = "" if col.is_nullable else " NOT NULL"
                desc = f"  -- {col.description}" if col.description else ""
                col_defs.append(f"  {col.name} {col.data_type}{nullable}{desc}")
            columns_str = ",\n".join(col_defs)
            parts.append(f"CREATE TABLE {qualified} (\n{columns_str}\n);")
        return "\n\n".join(parts)

    def _qualify_table_name(self, table: TableInfo) -> str:
        """Build a fully qualified table name depending on backend type."""
        backend = self._backend.backend_type
        if backend == "bigquery":
            prefix = f"`{table.catalog}.{table.schema_name}`." if table.catalog else ""
            return f"{prefix}`{table.table_name}`"
        if table.schema_name:
            return f"{table.schema_name}.{table.table_name}"
        return table.table_name

from __future__ import annotations

import structlog

from text_to_sql.db.base import DatabaseBackend
from text_to_sql.models.domain import SchemaInfo, TableInfo
from text_to_sql.schema.cache import SchemaCache

logger = structlog.get_logger()


class SchemaDiscoveryService:
    """Discovers and caches database schema metadata."""

    def __init__(
        self,
        backend: DatabaseBackend,
        cache: SchemaCache,
        include_tables: list[str] | None = None,
        exclude_tables: list[str] | None = None,
    ) -> None:
        self._backend = backend
        self._cache = cache
        self._include_tables = include_tables or []
        self._exclude_tables = exclude_tables or []

    async def get_schema(self, force_refresh: bool = False) -> SchemaInfo:
        cache_key = self._backend.backend_type
        if not force_refresh:
            cached = await self._cache.get(cache_key)
            if cached:
                logger.debug("schema_cache_hit", backend=cache_key)
                return cached

        tables = await self._backend.discover_tables()
        tables = self._filter_tables(tables)
        schema = SchemaInfo(tables=tables)
        await self._cache.set(cache_key, schema)
        logger.info("schema_discovered", backend=cache_key, table_count=len(tables))
        return schema

    def _filter_tables(self, tables: list[TableInfo]) -> list[TableInfo]:
        """Filter tables by include/exclude lists. Include takes precedence."""
        if self._include_tables:
            allowed = set(self._include_tables)
            return [t for t in tables if self._table_matches(t, allowed)]
        if self._exclude_tables:
            blocked = set(self._exclude_tables)
            return [t for t in tables if not self._table_matches(t, blocked)]
        return tables

    @staticmethod
    def _table_matches(table: TableInfo, names: set[str]) -> bool:
        """Check if table matches any name in the set (bare or qualified)."""
        if table.table_name in names:
            return True
        if table.schema_name:
            qualified = f"{table.schema_name}.{table.table_name}"
            if qualified in names:
                return True
        return False

    def schema_to_prompt_context(self, schema: SchemaInfo) -> str:
        """Format schema metadata as CREATE TABLE DDL for LLM context."""
        return "\n\n".join(self._render_table_ddl(t) for t in schema.tables)

    def schema_to_prompt_context_budgeted(
        self, schema: SchemaInfo, max_tokens: int,
    ) -> str:
        """Render tables until token budget is exhausted.

        Tables with descriptions are prioritized, then alphabetical.
        Omitted tables are listed in a comment so the LLM knows they exist.
        """
        from text_to_sql.llm.tokens import estimate_tokens

        # Sort: tables with descriptions first, then alphabetical
        sorted_tables = sorted(
            schema.tables,
            key=lambda t: (not bool(t.description), t.table_name),
        )

        included: list[str] = []
        omitted: list[str] = []
        used_tokens = 0

        for table in sorted_tables:
            ddl = self._render_table_ddl(table)
            ddl_tokens = estimate_tokens(ddl)
            if used_tokens + ddl_tokens <= max_tokens:
                included.append(ddl)
                used_tokens += ddl_tokens
            else:
                omitted.append(table.table_name)

        result = "\n\n".join(included)
        if omitted:
            result += f"\n\n-- Tables omitted: {', '.join(omitted)}"
        return result

    def _render_table_ddl(self, table: TableInfo) -> str:
        """Render a single table as CREATE TABLE DDL with description comments."""
        qualified = self._qualify_table_name(table)
        col_defs = []
        for col in table.columns:
            nullable = "" if col.is_nullable else " NOT NULL"
            desc = f"  -- {col.description}" if col.description else ""
            col_defs.append(f"  {col.name} {col.data_type}{nullable}{desc}")
        columns_str = ",\n".join(col_defs)
        header = f"-- {table.description}\n" if table.description else ""
        return f"{header}CREATE TABLE {qualified} (\n{columns_str}\n);"

    def _qualify_table_name(self, table: TableInfo) -> str:
        """Build a fully qualified table name depending on backend type."""
        backend = self._backend.backend_type
        if backend == "bigquery":
            prefix = f"`{table.catalog}.{table.schema_name}`." if table.catalog else ""
            return f"{prefix}`{table.table_name}`"
        if table.schema_name:
            return f"{table.schema_name}.{table.table_name}"
        return table.table_name

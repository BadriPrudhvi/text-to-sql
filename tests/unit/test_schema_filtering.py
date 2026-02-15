from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from text_to_sql.models.domain import ColumnInfo, TableInfo
from text_to_sql.schema.cache import SchemaCache
from text_to_sql.schema.discovery import SchemaDiscoveryService


def _make_tables() -> list[TableInfo]:
    return [
        TableInfo(schema_name="public", table_name="users", columns=[
            ColumnInfo(name="id", data_type="INTEGER"),
        ]),
        TableInfo(schema_name="public", table_name="orders", columns=[
            ColumnInfo(name="id", data_type="INTEGER"),
        ]),
        TableInfo(schema_name="audit", table_name="logs", columns=[
            ColumnInfo(name="id", data_type="INTEGER"),
        ]),
    ]


def _make_backend(tables: list[TableInfo]) -> AsyncMock:
    backend = AsyncMock()
    backend.backend_type = "sqlite"
    backend.discover_tables = AsyncMock(return_value=tables)
    return backend


@pytest.mark.asyncio
async def test_include_filters_to_allowlist() -> None:
    backend = _make_backend(_make_tables())
    service = SchemaDiscoveryService(
        backend, SchemaCache(ttl_seconds=3600), include_tables=["users"]
    )
    schema = await service.get_schema()
    assert [t.table_name for t in schema.tables] == ["users"]


@pytest.mark.asyncio
async def test_exclude_removes_from_list() -> None:
    backend = _make_backend(_make_tables())
    service = SchemaDiscoveryService(
        backend, SchemaCache(ttl_seconds=3600), exclude_tables=["orders"]
    )
    schema = await service.get_schema()
    names = [t.table_name for t in schema.tables]
    assert "orders" not in names
    assert "users" in names
    assert "logs" in names


@pytest.mark.asyncio
async def test_include_takes_precedence_over_exclude() -> None:
    backend = _make_backend(_make_tables())
    service = SchemaDiscoveryService(
        backend, SchemaCache(ttl_seconds=3600),
        include_tables=["users"], exclude_tables=["users"],
    )
    schema = await service.get_schema()
    assert [t.table_name for t in schema.tables] == ["users"]


@pytest.mark.asyncio
async def test_empty_filters_return_all() -> None:
    backend = _make_backend(_make_tables())
    service = SchemaDiscoveryService(backend, SchemaCache(ttl_seconds=3600))
    schema = await service.get_schema()
    assert len(schema.tables) == 3


@pytest.mark.asyncio
async def test_qualified_name_matching() -> None:
    backend = _make_backend(_make_tables())
    service = SchemaDiscoveryService(
        backend, SchemaCache(ttl_seconds=3600), include_tables=["audit.logs"]
    )
    schema = await service.get_schema()
    assert [t.table_name for t in schema.tables] == ["logs"]

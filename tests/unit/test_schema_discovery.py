from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from text_to_sql.models.domain import ColumnInfo, SchemaInfo, TableInfo
from text_to_sql.schema.cache import SchemaCache
from text_to_sql.schema.discovery import SchemaDiscoveryService


@pytest.fixture
def mock_backend() -> AsyncMock:
    backend = AsyncMock()
    backend.backend_type = "sqlite"
    backend.discover_tables = AsyncMock(
        return_value=[
            TableInfo(
                table_name="users",
                columns=[
                    ColumnInfo(name="id", data_type="INTEGER", is_nullable=False),
                    ColumnInfo(name="name", data_type="TEXT", is_nullable=True),
                ],
            )
        ]
    )
    return backend


@pytest.fixture
def cache() -> SchemaCache:
    return SchemaCache(ttl_seconds=3600)


@pytest.mark.asyncio
async def test_get_schema_calls_backend(
    mock_backend: AsyncMock, cache: SchemaCache
) -> None:
    service = SchemaDiscoveryService(mock_backend, cache)
    schema = await service.get_schema()
    assert len(schema.tables) == 1
    assert schema.tables[0].table_name == "users"
    mock_backend.discover_tables.assert_called_once()


@pytest.mark.asyncio
async def test_get_schema_uses_cache(
    mock_backend: AsyncMock, cache: SchemaCache
) -> None:
    service = SchemaDiscoveryService(mock_backend, cache)
    await service.get_schema()
    await service.get_schema()
    # Backend should only be called once due to caching
    mock_backend.discover_tables.assert_called_once()


@pytest.mark.asyncio
async def test_get_schema_force_refresh(
    mock_backend: AsyncMock, cache: SchemaCache
) -> None:
    service = SchemaDiscoveryService(mock_backend, cache)
    await service.get_schema()
    await service.get_schema(force_refresh=True)
    assert mock_backend.discover_tables.call_count == 2


def test_schema_to_prompt_context(
    mock_backend: AsyncMock, cache: SchemaCache
) -> None:
    service = SchemaDiscoveryService(mock_backend, cache)
    schema = SchemaInfo(
        tables=[
            TableInfo(
                table_name="users",
                columns=[
                    ColumnInfo(name="id", data_type="INTEGER", is_nullable=False),
                    ColumnInfo(name="name", data_type="TEXT"),
                ],
            )
        ]
    )
    context = service.schema_to_prompt_context(schema)
    assert "CREATE TABLE users" in context
    assert "id INTEGER NOT NULL" in context
    assert "name TEXT" in context


def test_schema_renders_table_description(
    mock_backend: AsyncMock, cache: SchemaCache
) -> None:
    service = SchemaDiscoveryService(mock_backend, cache)
    schema = SchemaInfo(
        tables=[
            TableInfo(
                table_name="users",
                description="Registered application users",
                columns=[
                    ColumnInfo(name="id", data_type="INTEGER", is_nullable=False),
                ],
            )
        ]
    )
    context = service.schema_to_prompt_context(schema)
    assert "-- Registered application users" in context
    assert "CREATE TABLE users" in context


def test_schema_renders_column_description(
    mock_backend: AsyncMock, cache: SchemaCache
) -> None:
    service = SchemaDiscoveryService(mock_backend, cache)
    schema = SchemaInfo(
        tables=[
            TableInfo(
                table_name="users",
                columns=[
                    ColumnInfo(
                        name="id", data_type="INTEGER",
                        is_nullable=False, description="Primary key",
                    ),
                ],
            )
        ]
    )
    context = service.schema_to_prompt_context(schema)
    assert "-- Primary key" in context


def test_budgeted_rendering_fits_all(
    mock_backend: AsyncMock, cache: SchemaCache
) -> None:
    service = SchemaDiscoveryService(mock_backend, cache)
    schema = SchemaInfo(
        tables=[
            TableInfo(table_name="users", columns=[
                ColumnInfo(name="id", data_type="INTEGER"),
            ]),
        ]
    )
    context = service.schema_to_prompt_context_budgeted(schema, max_tokens=10000)
    assert "CREATE TABLE users" in context
    assert "omitted" not in context


def test_budgeted_rendering_truncates(
    mock_backend: AsyncMock, cache: SchemaCache
) -> None:
    service = SchemaDiscoveryService(mock_backend, cache)
    tables = [
        TableInfo(table_name=f"table_{i}", columns=[
            ColumnInfo(name="id", data_type="INTEGER"),
            ColumnInfo(name="name", data_type="TEXT"),
        ])
        for i in range(50)
    ]
    schema = SchemaInfo(tables=tables)
    # Very small budget — should only fit a few tables
    context = service.schema_to_prompt_context_budgeted(schema, max_tokens=50)
    assert "Tables omitted" in context


def test_budgeted_rendering_zero_budget(
    mock_backend: AsyncMock, cache: SchemaCache
) -> None:
    service = SchemaDiscoveryService(mock_backend, cache)
    schema = SchemaInfo(
        tables=[
            TableInfo(table_name="users", columns=[
                ColumnInfo(name="id", data_type="INTEGER"),
            ]),
        ]
    )
    context = service.schema_to_prompt_context_budgeted(schema, max_tokens=0)
    assert "Tables omitted: users" in context


def test_budgeted_rendering_prioritizes_described_tables(
    mock_backend: AsyncMock, cache: SchemaCache
) -> None:
    service = SchemaDiscoveryService(mock_backend, cache)
    schema = SchemaInfo(
        tables=[
            TableInfo(table_name="z_no_desc", columns=[
                ColumnInfo(name="id", data_type="INTEGER"),
            ]),
            TableInfo(table_name="a_with_desc", description="Important table", columns=[
                ColumnInfo(name="id", data_type="INTEGER"),
            ]),
        ]
    )
    # Budget tight enough for only the described table
    context = service.schema_to_prompt_context_budgeted(schema, max_tokens=15)
    # Described table should be included first
    assert "a_with_desc" in context
    assert "Tables omitted: z_no_desc" in context

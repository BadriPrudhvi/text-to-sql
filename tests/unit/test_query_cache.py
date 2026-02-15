from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from text_to_sql.cache.query_cache import QueryCache, compute_schema_hash
from text_to_sql.models.domain import ColumnInfo, SchemaInfo, TableInfo


@pytest.fixture
def cache() -> QueryCache:
    return QueryCache(ttl_seconds=3600)


@pytest.mark.asyncio
async def test_cache_miss(cache: QueryCache) -> None:
    result = await cache.get("test question", "hash123")
    assert result is None


@pytest.mark.asyncio
async def test_cache_hit(cache: QueryCache) -> None:
    await cache.set("test question", "hash123", "SELECT 1", [{"x": 1}], "answer")
    result = await cache.get("test question", "hash123")
    assert result is not None
    assert result.sql == "SELECT 1"
    assert result.result == [{"x": 1}]
    assert result.answer == "answer"


@pytest.mark.asyncio
async def test_cache_normalized_question(cache: QueryCache) -> None:
    await cache.set("  How Many  Users?  ", "hash123", "SELECT 1", [], "answer")
    result = await cache.get("how many users?", "hash123")
    assert result is not None


@pytest.mark.asyncio
async def test_cache_different_schema_hash_misses(cache: QueryCache) -> None:
    await cache.set("test", "hash1", "SELECT 1", [], "answer")
    result = await cache.get("test", "hash2")
    assert result is None


@pytest.mark.asyncio
async def test_cache_ttl_expiration(cache: QueryCache) -> None:
    await cache.set("test", "hash123", "SELECT 1", [], "answer")
    # Manually expire the entry
    key = cache._make_key("test", "hash123")
    cache._cache[key].cached_at = datetime.now(timezone.utc) - timedelta(seconds=7200)
    result = await cache.get("test", "hash123")
    assert result is None


@pytest.mark.asyncio
async def test_invalidate_all(cache: QueryCache) -> None:
    await cache.set("q1", "hash", "SELECT 1", [], "a1")
    await cache.set("q2", "hash", "SELECT 2", [], "a2")
    await cache.invalidate_all()
    assert await cache.get("q1", "hash") is None
    assert await cache.get("q2", "hash") is None


@pytest.mark.asyncio
async def test_stats(cache: QueryCache) -> None:
    await cache.get("miss", "hash")
    await cache.set("hit", "hash", "SELECT 1", [], "a")
    await cache.get("hit", "hash")
    stats = await cache.stats()
    assert stats["entries"] == 1
    assert stats["hits"] == 1
    assert stats["misses"] == 1


def test_schema_hash_stability() -> None:
    schema = SchemaInfo(tables=[
        TableInfo(table_name="users", columns=[
            ColumnInfo(name="id", data_type="INT"),
            ColumnInfo(name="name", data_type="TEXT"),
        ]),
        TableInfo(table_name="orders", columns=[
            ColumnInfo(name="id", data_type="INT"),
        ]),
    ])
    h1 = compute_schema_hash(schema)
    h2 = compute_schema_hash(schema)
    assert h1 == h2


def test_schema_hash_changes_on_schema_change() -> None:
    schema1 = SchemaInfo(tables=[
        TableInfo(table_name="users", columns=[
            ColumnInfo(name="id", data_type="INT"),
        ]),
    ])
    schema2 = SchemaInfo(tables=[
        TableInfo(table_name="users", columns=[
            ColumnInfo(name="id", data_type="INT"),
            ColumnInfo(name="email", data_type="TEXT"),
        ]),
    ])
    assert compute_schema_hash(schema1) != compute_schema_hash(schema2)

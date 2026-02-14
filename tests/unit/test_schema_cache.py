from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from text_to_sql.models.domain import SchemaInfo
from text_to_sql.schema.cache import SchemaCache


@pytest.fixture
def cache() -> SchemaCache:
    return SchemaCache(ttl_seconds=60)


@pytest.mark.asyncio
async def test_cache_miss(cache: SchemaCache) -> None:
    result = await cache.get("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_cache_set_and_get(cache: SchemaCache) -> None:
    schema = SchemaInfo(tables=[])
    await cache.set("test", schema)
    result = await cache.get("test")
    assert result is not None
    assert result.tables == []


@pytest.mark.asyncio
async def test_cache_expiry(cache: SchemaCache) -> None:
    old_time = datetime.now(timezone.utc) - timedelta(seconds=120)
    schema = SchemaInfo(tables=[], discovered_at=old_time)
    await cache.set("test", schema)
    result = await cache.get("test")
    assert result is None


@pytest.mark.asyncio
async def test_cache_invalidate_specific(cache: SchemaCache) -> None:
    schema = SchemaInfo(tables=[])
    await cache.set("a", schema)
    await cache.set("b", schema)
    await cache.invalidate("a")
    assert await cache.get("a") is None
    assert await cache.get("b") is not None


@pytest.mark.asyncio
async def test_cache_invalidate_all(cache: SchemaCache) -> None:
    schema = SchemaInfo(tables=[])
    await cache.set("a", schema)
    await cache.set("b", schema)
    await cache.invalidate()
    assert await cache.get("a") is None
    assert await cache.get("b") is None

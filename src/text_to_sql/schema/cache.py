from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from text_to_sql.models.domain import SchemaInfo


class SchemaCache:
    """TTL-based in-memory cache for schema metadata."""

    def __init__(self, ttl_seconds: int = 3600) -> None:
        self._ttl = timedelta(seconds=ttl_seconds)
        self._cache: dict[str, SchemaInfo] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> SchemaInfo | None:
        async with self._lock:
            info = self._cache.get(key)
            if info is None:
                return None
            if (datetime.now(timezone.utc) - info.discovered_at) >= self._ttl:
                del self._cache[key]
                return None
            return info

    async def set(self, key: str, schema: SchemaInfo) -> None:
        async with self._lock:
            self._cache[key] = schema

    async def invalidate(self, key: str | None = None) -> None:
        async with self._lock:
            if key:
                self._cache.pop(key, None)
            else:
                self._cache.clear()

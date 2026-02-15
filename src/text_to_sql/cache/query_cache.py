from __future__ import annotations

import asyncio
import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from text_to_sql.models.domain import SchemaInfo


@dataclass
class CacheEntry:
    sql: str
    result: list[dict[str, Any]]
    answer: str
    cached_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def _normalize_question(question: str) -> str:
    """Lowercase, strip, collapse whitespace."""
    return re.sub(r"\s+", " ", question.strip().lower())


def compute_schema_hash(schema: SchemaInfo) -> str:
    """SHA256 of sorted table+column names for cache invalidation."""
    parts: list[str] = []
    for table in sorted(schema.tables, key=lambda t: t.table_name):
        cols = ",".join(sorted(c.name for c in table.columns))
        parts.append(f"{table.table_name}:{cols}")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


class QueryCache:
    """In-memory cache mapping (normalized question + schema hash) -> query result."""

    def __init__(self, ttl_seconds: int = 86400) -> None:
        self._cache: dict[str, CacheEntry] = {}
        self._ttl_seconds = ttl_seconds
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0

    async def get(self, question: str, schema_hash: str) -> CacheEntry | None:
        key = self._make_key(question, schema_hash)
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None
            age = (datetime.now(timezone.utc) - entry.cached_at).total_seconds()
            if age > self._ttl_seconds:
                del self._cache[key]
                self._misses += 1
                return None
            self._hits += 1
            return entry

    async def set(
        self,
        question: str,
        schema_hash: str,
        sql: str,
        result: list[dict[str, Any]],
        answer: str,
    ) -> None:
        key = self._make_key(question, schema_hash)
        async with self._lock:
            self._cache[key] = CacheEntry(sql=sql, result=result, answer=answer)

    async def invalidate_all(self) -> None:
        async with self._lock:
            self._cache.clear()

    async def stats(self) -> dict[str, int]:
        async with self._lock:
            return {
                "entries": len(self._cache),
                "hits": self._hits,
                "misses": self._misses,
            }

    def _make_key(self, question: str, schema_hash: str) -> str:
        normalized = _normalize_question(question)
        return hashlib.sha256(f"{normalized}|{schema_hash}".encode()).hexdigest()

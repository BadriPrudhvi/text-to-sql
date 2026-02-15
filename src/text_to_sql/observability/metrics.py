from __future__ import annotations

import asyncio
import time
from collections import defaultdict


class PipelineMetrics:
    """Lightweight in-memory metrics for pipeline observability."""

    def __init__(self) -> None:
        self._counters: dict[str, int] = defaultdict(int)
        self._lock = asyncio.Lock()
        self._start_time = time.monotonic()

    async def increment(self, name: str, amount: int = 1) -> None:
        async with self._lock:
            self._counters[name] += amount

    async def get_stats(self) -> dict[str, int | float]:
        async with self._lock:
            stats = dict(self._counters)
        stats["uptime_seconds"] = round(time.monotonic() - self._start_time, 1)
        return stats

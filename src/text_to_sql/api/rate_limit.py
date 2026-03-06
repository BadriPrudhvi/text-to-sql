from __future__ import annotations

import time
from collections import defaultdict


class RateLimiter:
    """Simple in-memory sliding window rate limiter."""

    _CLEANUP_INTERVAL = 300  # Prune stale keys every 5 minutes

    def __init__(self, max_requests: int, window_seconds: int = 60) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._last_cleanup = time.monotonic()

    def check(self, key: str) -> bool:
        """Return True if the request is allowed, False if rate limited."""
        now = time.monotonic()
        window_start = now - self._window_seconds

        # Periodic cleanup of stale keys to prevent unbounded growth
        if now - self._last_cleanup > self._CLEANUP_INTERVAL:
            self._prune_stale_keys(window_start)
            self._last_cleanup = now

        # Remove expired entries for this key
        self._requests[key] = [
            t for t in self._requests[key] if t > window_start
        ]

        if len(self._requests[key]) >= self._max_requests:
            return False

        self._requests[key].append(now)
        return True

    def _prune_stale_keys(self, window_start: float) -> None:
        """Remove keys with no recent requests."""
        stale = [k for k, v in self._requests.items() if not v or v[-1] <= window_start]
        for k in stale:
            del self._requests[k]

from __future__ import annotations

import time
from unittest.mock import patch

from text_to_sql.api.rate_limit import RateLimiter


def test_within_limit() -> None:
    limiter = RateLimiter(max_requests=5, window_seconds=60)
    for _ in range(5):
        assert limiter.check("client-1") is True


def test_exceeds_limit() -> None:
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    for _ in range(3):
        assert limiter.check("client-1") is True
    assert limiter.check("client-1") is False


def test_different_clients_independent() -> None:
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    assert limiter.check("client-1") is True
    assert limiter.check("client-1") is True
    assert limiter.check("client-1") is False
    # Different client still has quota
    assert limiter.check("client-2") is True


def test_window_reset() -> None:
    limiter = RateLimiter(max_requests=2, window_seconds=1)
    assert limiter.check("client-1") is True
    assert limiter.check("client-1") is True
    assert limiter.check("client-1") is False

    # Advance time past the window
    base_time = time.monotonic()
    with patch("text_to_sql.api.rate_limit.time") as mock_time:
        mock_time.monotonic.return_value = base_time + 2
        assert limiter.check("client-1") is True

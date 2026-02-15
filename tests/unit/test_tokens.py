from __future__ import annotations

from text_to_sql.llm.tokens import estimate_tokens


def test_estimate_tokens_nonempty() -> None:
    result = estimate_tokens("Hello, world!")
    assert result > 0


def test_estimate_tokens_empty() -> None:
    result = estimate_tokens("")
    # Should return at least 1 (or handle gracefully)
    assert result >= 0


def test_estimate_tokens_long_text() -> None:
    text = "word " * 1000  # ~5000 chars
    result = estimate_tokens(text)
    # Should be roughly 1000-1500 tokens
    assert 500 < result < 3000


def test_estimate_tokens_returns_int() -> None:
    result = estimate_tokens("test")
    assert isinstance(result, int)

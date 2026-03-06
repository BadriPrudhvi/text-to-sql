from __future__ import annotations

try:
    import tiktoken

    _ENCODER = tiktoken.get_encoding("cl100k_base")
except Exception:
    _ENCODER = None


def estimate_tokens(text: str) -> int:
    """Estimate token count for a string.

    Uses tiktoken if available, otherwise falls back to a ~4 chars/token heuristic.
    """
    if _ENCODER is not None:
        return len(_ENCODER.encode(text))
    # Heuristic: ~4 characters per token
    return max(1, len(text) // 4)

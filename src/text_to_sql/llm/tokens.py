from __future__ import annotations


def estimate_tokens(text: str) -> int:
    """Estimate token count for a string.

    Uses tiktoken if available, otherwise falls back to a ~4 chars/token heuristic.
    """
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except (ImportError, Exception):
        # Heuristic: ~4 characters per token
        return max(1, len(text) // 4)

from __future__ import annotations

from typing import Any

import structlog
from langchain_core.messages import BaseMessage
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = structlog.get_logger()


def create_invoke_with_retry(
    max_attempts: int = 3,
    min_wait: int = 2,
    max_wait: int = 10,
):
    """Create a retrying wrapper for LLM invocations.

    Returns an async function that wraps model.ainvoke() with exponential backoff
    retry on transient errors (connection, timeout).
    """

    @retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
        reraise=True,
        before_sleep=lambda retry_state: logger.warning(
            "llm_retry",
            attempt=retry_state.attempt_number,
            error=str(retry_state.outcome.exception()) if retry_state.outcome else "unknown",
        ),
    )
    async def invoke_with_retry(
        model: Any, messages: list[BaseMessage]
    ) -> BaseMessage:
        return await model.ainvoke(messages)

    return invoke_with_retry

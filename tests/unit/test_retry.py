from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from text_to_sql.llm.retry import create_invoke_with_retry


@pytest.mark.asyncio
async def test_invoke_succeeds_first_try() -> None:
    invoke = create_invoke_with_retry(max_attempts=3, min_wait=0, max_wait=0)
    model = AsyncMock()
    model.ainvoke.return_value = "response"
    result = await invoke(model, [])
    assert result == "response"
    assert model.ainvoke.call_count == 1


@pytest.mark.asyncio
async def test_invoke_retries_on_connection_error() -> None:
    invoke = create_invoke_with_retry(max_attempts=3, min_wait=0, max_wait=0)
    model = AsyncMock()
    model.ainvoke.side_effect = [ConnectionError("failed"), "response"]
    result = await invoke(model, [])
    assert result == "response"
    assert model.ainvoke.call_count == 2


@pytest.mark.asyncio
async def test_invoke_retries_on_timeout_error() -> None:
    invoke = create_invoke_with_retry(max_attempts=3, min_wait=0, max_wait=0)
    model = AsyncMock()
    model.ainvoke.side_effect = [TimeoutError("timeout"), "response"]
    result = await invoke(model, [])
    assert result == "response"
    assert model.ainvoke.call_count == 2


@pytest.mark.asyncio
async def test_invoke_no_retry_on_value_error() -> None:
    invoke = create_invoke_with_retry(max_attempts=3, min_wait=0, max_wait=0)
    model = AsyncMock()
    model.ainvoke.side_effect = ValueError("bad input")
    with pytest.raises(ValueError, match="bad input"):
        await invoke(model, [])
    assert model.ainvoke.call_count == 1


@pytest.mark.asyncio
async def test_invoke_exhausts_retries() -> None:
    invoke = create_invoke_with_retry(max_attempts=2, min_wait=0, max_wait=0)
    model = AsyncMock()
    model.ainvoke.side_effect = ConnectionError("failed")
    with pytest.raises(ConnectionError):
        await invoke(model, [])
    assert model.ainvoke.call_count == 2

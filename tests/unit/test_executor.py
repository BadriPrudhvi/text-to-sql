"""Tests for the analytical plan step executor agent."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, SystemMessage

from tests.conftest import FakeToolChatModel
from text_to_sql.pipeline.agents.executor import create_execute_plan_step_node
from text_to_sql.pipeline.agents.models import StepSQLResult


def _make_state(step_index: int = 0) -> dict[str, Any]:
    """Build a minimal executor state dict."""
    return {
        "messages": [SystemMessage(content="Schema: CREATE TABLE users (id INT, name TEXT)")],
        "current_step": step_index,
        "analysis_plan": [
            {"description": "Count users", "sql_hint": "SELECT count(*)"},
        ],
        "plan_results": [],
    }


def _make_db_backend(
    validate_result: list[str] | None = None,
    execute_result: list[dict[str, Any]] | None = None,
) -> AsyncMock:
    backend = AsyncMock()
    backend.validate_sql = AsyncMock(return_value=validate_result or [])
    backend.execute_sql = AsyncMock(return_value=execute_result or [{"count": 5}])
    return backend


def _noop_writer(event: Any) -> None:
    """No-op stream writer for tests."""


async def _passthrough_invoke(model: Any, messages: Any) -> Any:
    """Invoke helper that just calls ainvoke on the model."""
    return await model.ainvoke(messages)


@pytest.mark.asyncio
@patch("text_to_sql.pipeline.agents.executor.get_stream_writer", return_value=_noop_writer)
async def test_executor_uses_structured_output(_mock_writer: Any) -> None:
    """Executor should extract SQL from StepSQLResult when structured output works."""
    model = FakeToolChatModel(
        messages=iter([AIMessage(content="fallback")]),
        structured_responses={
            "StepSQLResult": StepSQLResult(sql="SELECT count(*) FROM users"),
        },
    )
    db = _make_db_backend()

    node = create_execute_plan_step_node(
        chat_model=model,
        db_backend=db,
        invoke_with_retry=_passthrough_invoke,
        dialect="sqlite",
    )
    result = await node(_make_state())

    assert len(result["plan_results"]) == 1
    step = result["plan_results"][0]
    assert step["sql"] == "SELECT count(*) FROM users"
    assert step["error"] is None


@pytest.mark.asyncio
@patch("text_to_sql.pipeline.agents.executor.get_stream_writer", return_value=_noop_writer)
async def test_executor_falls_back_to_raw_text(_mock_writer: Any) -> None:
    """When structured output fails, executor should fall back to raw text + cleaning."""
    model = FakeToolChatModel(
        messages=iter([
            AIMessage(content="SELECT count(*) FROM users;\nThis counts all users."),
        ]),
        # No structured_responses → with_structured_output returns self,
        # ainvoke returns AIMessage which is not StepSQLResult → falls into else branch
        structured_responses={},
    )
    db = _make_db_backend()

    node = create_execute_plan_step_node(
        chat_model=model,
        db_backend=db,
        invoke_with_retry=_passthrough_invoke,
        dialect="sqlite",
    )
    result = await node(_make_state())

    step = result["plan_results"][0]
    # clean_llm_sql should strip the explanation after semicolon
    assert step["sql"] == "SELECT count(*) FROM users"
    assert step["error"] is None


@pytest.mark.asyncio
@patch("text_to_sql.pipeline.agents.executor.get_stream_writer", return_value=_noop_writer)
async def test_executor_cleans_markdown_fences(_mock_writer: Any) -> None:
    """Executor should clean markdown code fences from SQL."""
    model = FakeToolChatModel(
        messages=iter([
            AIMessage(content="```sql\nSELECT 1;\n```\nExplanation here"),
        ]),
        structured_responses={},
    )
    db = _make_db_backend()

    node = create_execute_plan_step_node(
        chat_model=model,
        db_backend=db,
        invoke_with_retry=_passthrough_invoke,
        dialect="sqlite",
    )
    result = await node(_make_state())

    step = result["plan_results"][0]
    assert step["sql"] == "SELECT 1"

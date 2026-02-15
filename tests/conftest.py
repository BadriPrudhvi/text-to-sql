from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage


class FakeToolChatModel(GenericFakeChatModel):
    """GenericFakeChatModel with bind_tools support (no-op, returns self)."""

    def bind_tools(self, tools: Any, **kwargs: Any) -> FakeToolChatModel:
        return self


def make_tool_call_msg(sql: str, tool_call_id: str = "call_1") -> AIMessage:
    """Create an AIMessage with a run_query tool call."""
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": "run_query",
                "args": {"query": sql},
                "id": tool_call_id,
                "type": "tool_call",
            }
        ],
    )


def make_answer_msg(answer: str) -> AIMessage:
    """Create an AIMessage with a text answer (no tool calls)."""
    return AIMessage(content=answer)


def make_agent_responses(
    sql: str, answer: str, *, n: int = 20
) -> list[AIMessage]:
    """Generate n pairs of (tool call, answer) responses for the ReAct loop."""
    responses: list[AIMessage] = []
    for i in range(n):
        responses.append(make_tool_call_msg(sql, f"call_{i}"))
        responses.append(make_answer_msg(answer))
    return responses


@pytest.fixture(autouse=True)
def _set_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set environment variables for testing."""
    monkeypatch.setenv("PRIMARY_DB_TYPE", "sqlite")
    monkeypatch.setenv("SQLITE_URL", "sqlite+aiosqlite://")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-anthropic")
    monkeypatch.setenv("GOOGLE_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.setenv("STORAGE_TYPE", "memory")


@pytest.fixture
def mock_chat_model() -> FakeToolChatModel:
    """Create a FakeToolChatModel that returns tool call then answer."""
    return FakeToolChatModel(
        messages=iter(make_agent_responses("SELECT count(*) AS total FROM users", "There are 2 users.")),
    )


@pytest.fixture
async def app(mock_chat_model: FakeToolChatModel):
    """Create a test FastAPI app with mocked LLM."""
    with patch("text_to_sql.app.create_chat_model", return_value=mock_chat_model):
        from text_to_sql.app import create_app

        test_app = create_app()
        yield test_app


@pytest.fixture
async def client(app) -> AsyncClient:
    """Create an async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with LifespanManager(app):
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            from sqlalchemy import text

            db = app.state.db_backend
            async with db._engine.begin() as conn:
                await conn.execute(
                    text("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)")
                )
                await conn.execute(text("INSERT INTO users (id, name) VALUES (1, 'Alice')"))
                await conn.execute(text("INSERT INTO users (id, name) VALUES (2, 'Bob')"))
            yield c

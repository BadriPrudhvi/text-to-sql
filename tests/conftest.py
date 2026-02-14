from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def _set_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set environment variables for testing."""
    monkeypatch.setenv("PRIMARY_DB_TYPE", "sqlite")
    monkeypatch.setenv("SQLITE_URL", "sqlite+aiosqlite://")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-anthropic")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-openai")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")


@pytest.fixture
def mock_llm_router() -> MagicMock:
    """Create a mock LiteLLM router that returns predictable SQL."""
    router = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "SELECT count(*) AS total FROM users"
    mock_response.model = "test-model"
    router.acompletion = AsyncMock(return_value=mock_response)
    return router


@pytest.fixture
async def app(mock_llm_router: MagicMock):
    """Create a test FastAPI app with mocked LLM."""
    from unittest.mock import patch

    with patch("text_to_sql.app.create_llm_router", return_value=mock_llm_router):
        from text_to_sql.app import create_app

        test_app = create_app()
        yield test_app


@pytest.fixture
async def client(app) -> AsyncClient:
    """Create an async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # Trigger lifespan startup
        async with app.router.lifespan_context(app):
            # Create a test table so SQL execution works
            from sqlalchemy import text

            db = app.state.db_backend
            async with db._engine.begin() as conn:
                await conn.execute(
                    text("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)")
                )
                await conn.execute(text("INSERT INTO users (id, name) VALUES (1, 'Alice')"))
                await conn.execute(text("INSERT INTO users (id, name) VALUES (2, 'Bob')"))
            yield c

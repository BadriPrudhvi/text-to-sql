from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from langchain_core.language_models.fake_chat_models import FakeListChatModel


@pytest.fixture(autouse=True)
def _set_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set environment variables for testing."""
    monkeypatch.setenv("PRIMARY_DB_TYPE", "sqlite")
    monkeypatch.setenv("SQLITE_URL", "sqlite+aiosqlite://")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-anthropic")
    monkeypatch.setenv("GOOGLE_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")


@pytest.fixture
def mock_chat_model() -> FakeListChatModel:
    """Create a FakeListChatModel that returns predictable SQL."""
    return FakeListChatModel(
        responses=["SELECT count(*) AS total FROM users"] * 20,
    )


@pytest.fixture
async def app(mock_chat_model: FakeListChatModel):
    """Create a test FastAPI app with mocked LLM."""
    with patch("text_to_sql.app.create_chat_model", return_value=mock_chat_model):
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

from __future__ import annotations

from unittest.mock import patch

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from tests.conftest import FakeToolChatModel, make_agent_responses


@pytest.fixture
async def pending_client():
    """Client where the LLM returns SQL referencing a nonexistent table.

    This triggers validation errors, which routes to human_approval (PENDING).
    """
    bad_sql_model = FakeToolChatModel(
        messages=iter(make_agent_responses("SELECT count(*) FROM nonexistent_table", "There is 1 user.")),
    )

    with patch("text_to_sql.app.create_chat_model", return_value=bad_sql_model):
        from text_to_sql.app import create_app

        app = create_app()
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
                yield c


@pytest.mark.asyncio
async def test_approve_with_modified_sql(pending_client: AsyncClient) -> None:
    """Approve a query with validation errors by providing corrected SQL."""
    submit = await pending_client.post(
        "/api/query",
        json={"question": "How many items?"},
    )
    assert submit.json()["approval_status"] == "pending"
    query_id = submit.json()["query_id"]

    approve = await pending_client.post(
        f"/api/approve/{query_id}",
        json={"approved": True, "modified_sql": "SELECT count(*) FROM users"},
    )
    assert approve.status_code == 200
    data = approve.json()
    assert data["approval_status"] == "executed"
    assert data["result"] is not None
    assert data["answer"] is not None


@pytest.mark.asyncio
async def test_reject_query(pending_client: AsyncClient) -> None:
    submit = await pending_client.post(
        "/api/query",
        json={"question": "How many items?"},
    )
    query_id = submit.json()["query_id"]

    reject = await pending_client.post(
        f"/api/approve/{query_id}",
        json={"approved": False},
    )
    assert reject.status_code == 200
    assert reject.json()["approval_status"] == "rejected"

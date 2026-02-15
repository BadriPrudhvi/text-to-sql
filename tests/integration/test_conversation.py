from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_session(client: AsyncClient) -> None:
    resp = await client.post("/api/conversations")
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert data["session_id"]


@pytest.mark.asyncio
async def test_submit_query_in_session(client: AsyncClient) -> None:
    # Create session
    resp = await client.post("/api/conversations")
    session_id = resp.json()["session_id"]

    # Submit question
    resp = await client.post(
        f"/api/conversations/{session_id}/query",
        json={"question": "How many users are there?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["query_id"]
    assert data["approval_status"] == "executed"


@pytest.mark.asyncio
async def test_session_not_found(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/conversations/nonexistent/query",
        json={"question": "test"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_session_history(client: AsyncClient) -> None:
    # Create session and submit a query
    resp = await client.post("/api/conversations")
    session_id = resp.json()["session_id"]

    await client.post(
        f"/api/conversations/{session_id}/query",
        json={"question": "How many users are there?"},
    )

    # Get history
    resp = await client.get(f"/api/conversations/{session_id}/history")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == session_id
    assert data["total"] == 1
    assert len(data["queries"]) == 1


@pytest.mark.asyncio
async def test_session_isolation(client: AsyncClient) -> None:
    """Queries in one session don't appear in another."""
    # Create two sessions
    r1 = await client.post("/api/conversations")
    r2 = await client.post("/api/conversations")
    s1 = r1.json()["session_id"]
    s2 = r2.json()["session_id"]

    # Submit query only in session 1
    await client.post(
        f"/api/conversations/{s1}/query",
        json={"question": "How many users are there?"},
    )

    # Session 2 should have no queries
    resp = await client.get(f"/api/conversations/{s2}/history")
    assert resp.json()["total"] == 0

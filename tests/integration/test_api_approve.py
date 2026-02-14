from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_approve_and_execute(client: AsyncClient) -> None:
    # Submit question first
    submit = await client.post(
        "/api/query",
        json={"question": "How many users?"},
    )
    query_id = submit.json()["query_id"]

    # Approve
    approve = await client.post(
        f"/api/approve/{query_id}",
        json={"approved": True},
    )
    assert approve.status_code == 200
    data = approve.json()
    assert data["approval_status"] == "executed"
    assert data["result"] is not None


@pytest.mark.asyncio
async def test_reject_query(client: AsyncClient) -> None:
    submit = await client.post(
        "/api/query",
        json={"question": "How many users?"},
    )
    query_id = submit.json()["query_id"]

    reject = await client.post(
        f"/api/approve/{query_id}",
        json={"approved": False},
    )
    assert reject.status_code == 200
    data = reject.json()
    assert data["approval_status"] == "rejected"


@pytest.mark.asyncio
async def test_approve_with_modified_sql(client: AsyncClient) -> None:
    submit = await client.post(
        "/api/query",
        json={"question": "How many users?"},
    )
    query_id = submit.json()["query_id"]

    approve = await client.post(
        f"/api/approve/{query_id}",
        json={"approved": True, "modified_sql": "SELECT 1"},
    )
    assert approve.status_code == 200
    assert approve.json()["approval_status"] == "executed"

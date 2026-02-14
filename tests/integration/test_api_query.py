from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_submit_query(client: AsyncClient) -> None:
    response = await client.post(
        "/api/query",
        json={"question": "How many users are there?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["question"] == "How many users are there?"
    assert data["generated_sql"]
    assert data["approval_status"] == "pending"
    assert "query_id" in data


@pytest.mark.asyncio
async def test_submit_query_empty_question(client: AsyncClient) -> None:
    response = await client.post(
        "/api/query",
        json={"question": ""},
    )
    assert response.status_code == 422

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_empty_history(client: AsyncClient) -> None:
    response = await client.get("/api/history")
    assert response.status_code == 200
    data = response.json()
    assert data["queries"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_history_after_query(client: AsyncClient) -> None:
    # Submit a query
    await client.post(
        "/api/query",
        json={"question": "How many users?"},
    )

    response = await client.get("/api/history")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["queries"][0]["natural_language"] == "How many users?"


@pytest.mark.asyncio
async def test_history_pagination(client: AsyncClient) -> None:
    # Submit multiple queries
    for i in range(3):
        await client.post(
            "/api/query",
            json={"question": f"Question {i}"},
        )

    response = await client.get("/api/history?limit=2&offset=0")
    data = response.json()
    assert len(data["queries"]) == 2
    assert data["total"] == 3

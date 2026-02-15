from __future__ import annotations

import asyncio

import pytest

from text_to_sql.store.session import InMemorySessionStore


@pytest.fixture
def session_store() -> InMemorySessionStore:
    return InMemorySessionStore()


@pytest.mark.asyncio
async def test_create_session(session_store: InMemorySessionStore) -> None:
    session = await session_store.create()
    assert session.id
    assert session.created_at
    assert session.last_activity
    assert session.query_ids == []


@pytest.mark.asyncio
async def test_get_session(session_store: InMemorySessionStore) -> None:
    session = await session_store.create()
    retrieved = await session_store.get(session.id)
    assert retrieved.id == session.id


@pytest.mark.asyncio
async def test_get_nonexistent_session(session_store: InMemorySessionStore) -> None:
    with pytest.raises(KeyError, match="not found"):
        await session_store.get("nonexistent-id")


@pytest.mark.asyncio
async def test_update_activity(session_store: InMemorySessionStore) -> None:
    session = await session_store.create()
    original_activity = session.last_activity

    updated = await session_store.update_activity(session.id, "query-1")
    assert "query-1" in updated.query_ids
    assert updated.last_activity >= original_activity


@pytest.mark.asyncio
async def test_update_activity_deduplicates_query_ids(
    session_store: InMemorySessionStore,
) -> None:
    session = await session_store.create()
    await session_store.update_activity(session.id, "query-1")
    await session_store.update_activity(session.id, "query-1")
    updated = await session_store.get(session.id)
    assert updated.query_ids.count("query-1") == 1


@pytest.mark.asyncio
async def test_update_activity_nonexistent_session(
    session_store: InMemorySessionStore,
) -> None:
    with pytest.raises(KeyError, match="not found"):
        await session_store.update_activity("nonexistent-id", "query-1")


@pytest.mark.asyncio
async def test_list_sessions(session_store: InMemorySessionStore) -> None:
    s1 = await session_store.create()
    s2 = await session_store.create()
    sessions = await session_store.list_sessions()
    assert len(sessions) == 2
    # Most recent first
    assert sessions[0].id == s2.id
    assert sessions[1].id == s1.id


@pytest.mark.asyncio
async def test_list_sessions_pagination(session_store: InMemorySessionStore) -> None:
    for _ in range(5):
        await session_store.create()
    page = await session_store.list_sessions(limit=2, offset=1)
    assert len(page) == 2


@pytest.mark.asyncio
async def test_concurrent_creates(session_store: InMemorySessionStore) -> None:
    tasks = [session_store.create() for _ in range(20)]
    sessions = await asyncio.gather(*tasks)
    assert len(set(s.id for s in sessions)) == 20
    all_sessions = await session_store.list_sessions(limit=100)
    assert len(all_sessions) == 20

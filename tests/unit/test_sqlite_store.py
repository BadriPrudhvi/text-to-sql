from __future__ import annotations

import pytest

from text_to_sql.models.domain import ApprovalStatus, QueryRecord
from text_to_sql.store.sqlite_store import SQLiteQueryStore


@pytest.fixture
async def sqlite_store(tmp_path) -> SQLiteQueryStore:
    store = SQLiteQueryStore(str(tmp_path / "test.db"))
    await store.init_db()
    yield store
    await store.close()


@pytest.mark.asyncio
async def test_save_and_get(sqlite_store: SQLiteQueryStore) -> None:
    record = QueryRecord(
        natural_language="How many users?",
        database_type="sqlite",
        generated_sql="SELECT count(*) FROM users",
    )
    await sqlite_store.save(record)
    retrieved = await sqlite_store.get(record.id)
    assert retrieved.natural_language == "How many users?"
    assert retrieved.generated_sql == "SELECT count(*) FROM users"


@pytest.mark.asyncio
async def test_get_nonexistent(sqlite_store: SQLiteQueryStore) -> None:
    with pytest.raises(KeyError, match="not found"):
        await sqlite_store.get("nonexistent")


@pytest.mark.asyncio
async def test_save_updates_existing(sqlite_store: SQLiteQueryStore) -> None:
    record = QueryRecord(
        natural_language="test",
        database_type="sqlite",
    )
    await sqlite_store.save(record)

    record.approval_status = ApprovalStatus.EXECUTED
    record.result = [{"count": 42}]
    await sqlite_store.save(record)

    retrieved = await sqlite_store.get(record.id)
    assert retrieved.approval_status == ApprovalStatus.EXECUTED
    assert retrieved.result == [{"count": 42}]


@pytest.mark.asyncio
async def test_list_ordered_by_created_at(sqlite_store: SQLiteQueryStore) -> None:
    for i in range(3):
        record = QueryRecord(natural_language=f"q{i}", database_type="sqlite")
        await sqlite_store.save(record)

    records = await sqlite_store.list(limit=10)
    assert len(records) == 3
    # Newest first
    assert records[0].natural_language == "q2"


@pytest.mark.asyncio
async def test_list_pagination(sqlite_store: SQLiteQueryStore) -> None:
    for i in range(5):
        await sqlite_store.save(
            QueryRecord(natural_language=f"q{i}", database_type="sqlite")
        )
    page = await sqlite_store.list(limit=2, offset=1)
    assert len(page) == 2


@pytest.mark.asyncio
async def test_count(sqlite_store: SQLiteQueryStore) -> None:
    assert await sqlite_store.count() == 0
    await sqlite_store.save(
        QueryRecord(natural_language="test", database_type="sqlite")
    )
    assert await sqlite_store.count() == 1


@pytest.mark.asyncio
async def test_json_roundtrip_validation_errors(sqlite_store: SQLiteQueryStore) -> None:
    record = QueryRecord(
        natural_language="test",
        database_type="sqlite",
        validation_errors=["error 1", "error 2"],
    )
    await sqlite_store.save(record)
    retrieved = await sqlite_store.get(record.id)
    assert retrieved.validation_errors == ["error 1", "error 2"]


@pytest.mark.asyncio
async def test_json_roundtrip_result(sqlite_store: SQLiteQueryStore) -> None:
    record = QueryRecord(
        natural_language="test",
        database_type="sqlite",
        result=[{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
    )
    await sqlite_store.save(record)
    retrieved = await sqlite_store.get(record.id)
    assert retrieved.result == [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]


@pytest.mark.asyncio
async def test_init_db_idempotent(tmp_path) -> None:
    db_path = str(tmp_path / "test.db")
    store = SQLiteQueryStore(db_path)
    await store.init_db()
    await store.init_db()  # Should not raise
    await store.close()


@pytest.mark.asyncio
async def test_session_id_persists(sqlite_store: SQLiteQueryStore) -> None:
    record = QueryRecord(
        natural_language="test",
        database_type="sqlite",
        session_id="session-123",
    )
    await sqlite_store.save(record)
    retrieved = await sqlite_store.get(record.id)
    assert retrieved.session_id == "session-123"


@pytest.mark.asyncio
async def test_list_by_session(sqlite_store: SQLiteQueryStore) -> None:
    for i in range(3):
        await sqlite_store.save(
            QueryRecord(
                natural_language=f"q{i}",
                database_type="sqlite",
                session_id="s1" if i < 2 else "s2",
            )
        )
    s1_records = await sqlite_store.list_by_session("s1")
    assert len(s1_records) == 2
    s2_records = await sqlite_store.list_by_session("s2")
    assert len(s2_records) == 1

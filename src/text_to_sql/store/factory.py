from __future__ import annotations

from typing import Any

from text_to_sql.store.memory import InMemoryQueryStore
from text_to_sql.store.session import InMemorySessionStore
from text_to_sql.store.sqlite_session_store import SQLiteSessionStore
from text_to_sql.store.sqlite_store import SQLiteQueryStore


async def create_stores(
    storage_type: str, sqlite_path: str = "./pipeline.db"
) -> dict[str, Any]:
    """Create query and session stores based on storage_type.

    Returns dict with keys: query_store, session_store, and optional cleanup coroutine.
    """
    if storage_type == "sqlite":
        query_store = SQLiteQueryStore(sqlite_path)
        await query_store.init_db()

        # Share the same DB connection for sessions
        assert query_store._db is not None
        session_store = SQLiteSessionStore(query_store._db)
        await session_store.init_db()

        return {
            "query_store": query_store,
            "session_store": session_store,
            "cleanup": query_store.close,
        }

    return {
        "query_store": InMemoryQueryStore(),
        "session_store": InMemorySessionStore(),
        "cleanup": None,
    }

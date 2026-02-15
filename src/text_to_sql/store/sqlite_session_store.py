from __future__ import annotations

from datetime import datetime, timezone

import aiosqlite

from text_to_sql.models.domain import SessionInfo

_CREATE_SESSIONS = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    last_activity TEXT NOT NULL
)
"""


class SQLiteSessionStore:
    """Persistent session store backed by SQLite via aiosqlite.

    Session → query mapping uses query_records.session_id (no separate join table).
    """

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def init_db(self) -> None:
        await self._db.execute(_CREATE_SESSIONS)
        await self._db.commit()

    async def create(self) -> SessionInfo:
        session = SessionInfo()
        await self._db.execute(
            "INSERT INTO sessions (id, created_at, last_activity) VALUES (?, ?, ?)",
            (session.id, session.created_at.isoformat(), session.last_activity.isoformat()),
        )
        await self._db.commit()
        return session

    async def get(self, session_id: str) -> SessionInfo:
        cursor = await self._db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        row = await cursor.fetchone()
        if not row:
            raise KeyError(f"Session {session_id} not found")

        # Get query_ids from query_records table
        q_cursor = await self._db.execute(
            "SELECT id FROM query_records WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,),
        )
        q_rows = await q_cursor.fetchall()
        query_ids = [r[0] for r in q_rows]

        return SessionInfo(
            id=row[0],
            created_at=datetime.fromisoformat(row[1]),
            last_activity=datetime.fromisoformat(row[2]),
            query_ids=query_ids,
        )

    async def update_activity(self, session_id: str, query_id: str) -> SessionInfo:
        # Verify session exists
        cursor = await self._db.execute("SELECT id FROM sessions WHERE id = ?", (session_id,))
        if not await cursor.fetchone():
            raise KeyError(f"Session {session_id} not found")

        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            "UPDATE sessions SET last_activity = ? WHERE id = ?",
            (now, session_id),
        )
        await self._db.commit()
        # query_id mapping is implicit via query_records.session_id
        return await self.get(session_id)

    async def list_sessions(self, limit: int = 50, offset: int = 0) -> list[SessionInfo]:
        cursor = await self._db.execute(
            "SELECT * FROM sessions ORDER BY last_activity DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cursor.fetchall()
        sessions = []
        for row in rows:
            sessions.append(
                SessionInfo(
                    id=row[0],
                    created_at=datetime.fromisoformat(row[1]),
                    last_activity=datetime.fromisoformat(row[2]),
                )
            )
        return sessions

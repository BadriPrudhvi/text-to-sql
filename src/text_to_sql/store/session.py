from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Protocol

from text_to_sql.models.domain import SessionInfo


class SessionStore(Protocol):
    """Protocol for session persistence."""

    async def create(self) -> SessionInfo: ...

    async def get(self, session_id: str) -> SessionInfo: ...

    async def update_activity(self, session_id: str, query_id: str) -> SessionInfo: ...

    async def list_sessions(self, limit: int = 50, offset: int = 0) -> list[SessionInfo]: ...


class InMemorySessionStore:
    """Thread-safe in-memory session store."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionInfo] = {}
        self._lock = asyncio.Lock()

    async def create(self) -> SessionInfo:
        session = SessionInfo()
        async with self._lock:
            self._sessions[session.id] = session
        return session

    async def get(self, session_id: str) -> SessionInfo:
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                raise KeyError(f"Session {session_id} not found")
            return session

    async def update_activity(self, session_id: str, query_id: str) -> SessionInfo:
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                raise KeyError(f"Session {session_id} not found")
            session.last_activity = datetime.now(timezone.utc)
            if query_id not in session.query_ids:
                session.query_ids.append(query_id)
            return session

    async def list_sessions(self, limit: int = 50, offset: int = 0) -> list[SessionInfo]:
        async with self._lock:
            all_sessions = sorted(
                self._sessions.values(),
                key=lambda s: s.last_activity,
                reverse=True,
            )
            return all_sessions[offset : offset + limit]

from __future__ import annotations

import json
from datetime import datetime

import aiosqlite

from text_to_sql.models.domain import ApprovalStatus, QueryRecord

_CREATE_QUERY_RECORDS = """
CREATE TABLE IF NOT EXISTS query_records (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    natural_language TEXT NOT NULL,
    database_type TEXT NOT NULL,
    generated_sql TEXT DEFAULT '',
    validation_errors TEXT DEFAULT '[]',
    approval_status TEXT DEFAULT 'pending',
    result TEXT,
    answer TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    approved_at TEXT,
    executed_at TEXT
)
"""

_CREATE_IDX_SESSION = """
CREATE INDEX IF NOT EXISTS idx_query_session ON query_records(session_id)
"""

_CREATE_IDX_STATUS = """
CREATE INDEX IF NOT EXISTS idx_query_status ON query_records(approval_status)
"""


def _serialize_dt(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _deserialize_dt(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s else None


def _record_to_row(record: QueryRecord) -> dict:
    return {
        "id": record.id,
        "session_id": record.session_id,
        "natural_language": record.natural_language,
        "database_type": record.database_type,
        "generated_sql": record.generated_sql,
        "validation_errors": json.dumps(record.validation_errors),
        "approval_status": record.approval_status.value,
        "result": json.dumps(record.result, default=str) if record.result is not None else None,
        "answer": record.answer,
        "error": record.error,
        "created_at": record.created_at.isoformat(),
        "approved_at": _serialize_dt(record.approved_at),
        "executed_at": _serialize_dt(record.executed_at),
    }


def _row_to_record(row: aiosqlite.Row) -> QueryRecord:
    return QueryRecord(
        id=row[0],
        session_id=row[1],
        natural_language=row[2],
        database_type=row[3],
        generated_sql=row[4] or "",
        validation_errors=json.loads(row[5]) if row[5] else [],
        approval_status=ApprovalStatus(row[6]),
        result=json.loads(row[7]) if row[7] else None,
        answer=row[8],
        error=row[9],
        created_at=datetime.fromisoformat(row[10]),
        approved_at=_deserialize_dt(row[11]),
        executed_at=_deserialize_dt(row[12]),
    )


class SQLiteQueryStore:
    """Persistent query store backed by SQLite via aiosqlite."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def init_db(self) -> None:
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.execute(_CREATE_QUERY_RECORDS)
        await self._db.execute(_CREATE_IDX_SESSION)
        await self._db.execute(_CREATE_IDX_STATUS)
        await self._db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    async def save(self, record: QueryRecord) -> None:
        assert self._db is not None
        row = _record_to_row(record)
        await self._db.execute(
            """INSERT OR REPLACE INTO query_records
            (id, session_id, natural_language, database_type, generated_sql,
             validation_errors, approval_status, result, answer, error,
             created_at, approved_at, executed_at)
            VALUES (:id, :session_id, :natural_language, :database_type, :generated_sql,
                    :validation_errors, :approval_status, :result, :answer, :error,
                    :created_at, :approved_at, :executed_at)""",
            row,
        )
        await self._db.commit()

    async def get(self, query_id: str) -> QueryRecord:
        assert self._db is not None
        cursor = await self._db.execute(
            "SELECT * FROM query_records WHERE id = ?", (query_id,)
        )
        row = await cursor.fetchone()
        if not row:
            raise KeyError(f"Query {query_id} not found")
        return _row_to_record(row)

    async def list(self, limit: int = 50, offset: int = 0) -> list[QueryRecord]:
        assert self._db is not None
        cursor = await self._db.execute(
            "SELECT * FROM query_records ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cursor.fetchall()
        return [_row_to_record(row) for row in rows]

    async def count(self) -> int:
        assert self._db is not None
        cursor = await self._db.execute("SELECT COUNT(*) FROM query_records")
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def list_by_session(self, session_id: str) -> list[QueryRecord]:
        assert self._db is not None
        cursor = await self._db.execute(
            "SELECT * FROM query_records WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,),
        )
        rows = await cursor.fetchall()
        return [_row_to_record(row) for row in rows]

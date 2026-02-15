from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool

from text_to_sql.db.base import DatabaseBackend


def create_run_query_tool(db_backend: DatabaseBackend):
    """Create a run_query tool bound to the given database backend."""

    @tool
    async def run_query(query: str) -> str:
        """Execute a read-only SQL query against the database and return results as JSON.

        Args:
            query: The SQL query to execute. Must be a SELECT or WITH statement.
        """
        result: list[dict[str, Any]] = await db_backend.execute_sql(query)
        return json.dumps(result, default=str)

    return run_query

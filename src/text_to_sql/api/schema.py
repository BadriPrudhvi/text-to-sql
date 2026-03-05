from __future__ import annotations

from fastapi import APIRouter, Request

from text_to_sql.schema.cache import SchemaCache
from text_to_sql.schema.discovery import SchemaDiscoveryService

router = APIRouter()


@router.get("/schema/tables")
async def get_schema_tables(request: Request) -> dict:
    """Return table names, descriptions, and columns from the schema cache."""
    settings = request.app.state.settings
    db_backend = request.app.state.db_backend
    schema_cache: SchemaCache = request.app.state.schema_cache

    discovery = SchemaDiscoveryService(
        backend=db_backend,
        cache=schema_cache,
        include_tables=settings.schema_include_tables or None,
        exclude_tables=settings.schema_exclude_tables or None,
    )
    schema = await discovery.get_schema()

    tables = [
        {
            "name": t.table_name,
            "description": t.description or None,
            "columns": [
                {"name": c.name, "type": c.data_type}
                for c in t.columns
            ],
        }
        for t in schema.tables
    ]
    return {"tables": tables}

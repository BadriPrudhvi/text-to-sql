from __future__ import annotations

from text_to_sql.config import DatabaseType, Settings
from text_to_sql.db.base import DatabaseBackend
from text_to_sql.db.bigquery import BigQueryBackend
from text_to_sql.db.postgres import PostgresBackend
from text_to_sql.db.sqlite import SqliteBackend


async def create_database_backend(settings: Settings) -> DatabaseBackend:
    """Create and connect the appropriate database backend based on config."""
    backend: DatabaseBackend
    match settings.primary_db_type:
        case DatabaseType.BIGQUERY:
            backend = BigQueryBackend(
                project=settings.bigquery_project,
                dataset=settings.bigquery_dataset,
                credentials_path=settings.bigquery_credentials_path,
            )
        case DatabaseType.POSTGRES:
            backend = PostgresBackend(url=settings.postgres_url)
        case DatabaseType.SQLITE:
            backend = SqliteBackend(
                url=settings.sqlite_url,
                metadata_path=settings.sqlite_metadata_path,
            )

    await backend.connect()
    return backend

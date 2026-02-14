from __future__ import annotations

import asyncio
from functools import partial
from typing import Any

import structlog

from text_to_sql.db.base import check_read_only
from text_to_sql.models.domain import ColumnInfo, TableInfo

logger = structlog.get_logger()


class BigQueryBackend:
    """BigQuery database backend using INFORMATION_SCHEMA for discovery."""

    def __init__(self, project: str, dataset: str, credentials_path: str = "") -> None:
        self._project = project
        self._dataset = dataset
        self._credentials_path = credentials_path
        self._client: Any = None

    async def connect(self) -> None:
        from google.cloud import bigquery

        def _create_client() -> Any:
            if self._credentials_path:
                from google.oauth2 import service_account

                credentials = service_account.Credentials.from_service_account_file(
                    self._credentials_path
                )
                return bigquery.Client(project=self._project, credentials=credentials)
            return bigquery.Client(project=self._project)

        self._client = await asyncio.get_event_loop().run_in_executor(None, _create_client)
        logger.info("bigquery_connected", project=self._project, dataset=self._dataset)

    async def close(self) -> None:
        if self._client:
            self._client.close()

    async def discover_tables(self) -> list[TableInfo]:
        query = f"""
            SELECT
                t.table_catalog,
                t.table_schema,
                t.table_name,
                t.table_type,
                c.column_name,
                c.data_type,
                c.is_nullable,
                c.column_name AS description
            FROM `{self._project}.{self._dataset}.INFORMATION_SCHEMA.TABLES` t
            JOIN `{self._project}.{self._dataset}.INFORMATION_SCHEMA.COLUMNS` c
                ON t.table_name = c.table_name
                AND t.table_schema = c.table_schema
            ORDER BY t.table_name, c.ordinal_position
        """

        def _run_query() -> list[dict[str, Any]]:
            result = self._client.query(query)
            return [dict(row) for row in result]

        rows = await asyncio.get_event_loop().run_in_executor(None, _run_query)

        tables_map: dict[str, TableInfo] = {}
        for row in rows:
            key = f"{row['table_schema']}.{row['table_name']}"
            if key not in tables_map:
                tables_map[key] = TableInfo(
                    catalog=row.get("table_catalog", ""),
                    schema_name=row.get("table_schema", ""),
                    table_name=row["table_name"],
                    table_type=row.get("table_type", "TABLE"),
                    columns=[],
                )
            # TableInfo is frozen, so we build columns as a list and recreate
            cols = list(tables_map[key].columns)
            cols.append(
                ColumnInfo(
                    name=row["column_name"],
                    data_type=row["data_type"],
                    is_nullable=row.get("is_nullable", "YES") == "YES",
                    description="",
                )
            )
            tables_map[key] = tables_map[key].model_copy(update={"columns": cols})

        tables = list(tables_map.values())
        logger.info("bigquery_schema_discovered", table_count=len(tables))
        return tables

    async def validate_sql(self, sql: str) -> list[str]:
        errors = check_read_only(sql)
        if errors:
            return errors

        from google.cloud.bigquery import QueryJobConfig

        def _dry_run() -> list[str]:
            job_config = QueryJobConfig(dry_run=True, use_query_cache=False)
            try:
                self._client.query(sql, job_config=job_config)
                return []
            except Exception as e:
                return [str(e)]

        return await asyncio.get_event_loop().run_in_executor(None, _dry_run)

    async def execute_sql(self, sql: str) -> list[dict[str, Any]]:
        errors = check_read_only(sql)
        if errors:
            raise ValueError(errors[0])

        def _execute() -> list[dict[str, Any]]:
            result = self._client.query(sql)
            return [dict(row) for row in result]

        rows = await asyncio.get_event_loop().run_in_executor(None, _execute)
        logger.info("bigquery_query_executed", row_count=len(rows))
        return rows

    @property
    def backend_type(self) -> str:
        return "bigquery"

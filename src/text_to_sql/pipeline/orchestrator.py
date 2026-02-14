from __future__ import annotations

from datetime import datetime, timezone

import structlog
from litellm import Router

from text_to_sql.config import Settings
from text_to_sql.db.base import DatabaseBackend
from text_to_sql.llm.sql_generator import SQLGenerator
from text_to_sql.models.domain import ApprovalStatus, QueryRecord
from text_to_sql.pipeline.approval import ApprovalManager
from text_to_sql.schema.cache import SchemaCache
from text_to_sql.schema.discovery import SchemaDiscoveryService
from text_to_sql.store.base import QueryStore

logger = structlog.get_logger()


class PipelineOrchestrator:
    """Coordinates the full NL -> SQL -> Approval -> Execution pipeline."""

    def __init__(
        self,
        db_backend: DatabaseBackend,
        schema_cache: SchemaCache,
        llm_router: Router,
        query_store: QueryStore,
        settings: Settings,
    ) -> None:
        self._schema_service = SchemaDiscoveryService(db_backend, schema_cache)
        self._sql_generator = SQLGenerator(llm_router, settings)
        self._approval_manager = ApprovalManager(query_store)
        self._db = db_backend
        self._store = query_store

    @property
    def approval_manager(self) -> ApprovalManager:
        return self._approval_manager

    async def submit_question(self, question: str) -> QueryRecord:
        """Phase 1: Generate SQL from a natural language question and queue for approval."""
        # 1. Discover/cache schema
        schema = await self._schema_service.get_schema()
        schema_context = self._schema_service.schema_to_prompt_context(schema)

        # 2. Generate SQL via LLM
        sql = await self._sql_generator.generate(
            question=question,
            schema_context=schema_context,
            dialect=self._db.backend_type,
        )

        # 3. Validate SQL
        errors = await self._db.validate_sql(sql)

        # 4. Create record and submit for approval
        record = QueryRecord(
            natural_language=question,
            database_type=self._db.backend_type,
            generated_sql=sql,
            validation_errors=errors,
        )
        record = await self._approval_manager.submit_for_approval(record)

        logger.info(
            "question_submitted",
            query_id=record.id,
            question=question,
            sql=sql,
            validation_errors=errors,
        )
        return record

    async def execute_approved(self, query_id: str) -> QueryRecord:
        """Phase 2: Execute an approved query."""
        record = await self._store.get(query_id)
        if record.approval_status != ApprovalStatus.APPROVED:
            raise ValueError(
                f"Query {query_id} must be approved before execution "
                f"(current status: {record.approval_status.value})"
            )

        try:
            result = await self._db.execute_sql(record.generated_sql)
            record.result = result
            record.approval_status = ApprovalStatus.EXECUTED
            record.executed_at = datetime.now(timezone.utc)
            logger.info("query_executed", query_id=query_id, row_count=len(result))
        except Exception as e:
            record.error = str(e)
            record.approval_status = ApprovalStatus.FAILED
            logger.error("query_execution_failed", query_id=query_id, error=str(e))

        await self._store.save(record)
        return record

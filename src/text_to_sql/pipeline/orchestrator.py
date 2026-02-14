from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from langgraph.types import Command

from text_to_sql.models.domain import ApprovalStatus, QueryRecord
from text_to_sql.pipeline.approval import ApprovalManager
from text_to_sql.store.base import QueryStore

logger = structlog.get_logger()


class PipelineOrchestrator:
    """Coordinates the full NL -> SQL -> Approval -> Execution pipeline via LangGraph."""

    def __init__(
        self,
        graph: Any,
        query_store: QueryStore,
    ) -> None:
        self._graph = graph
        self._store = query_store
        self._approval_manager = ApprovalManager(query_store)

    @property
    def approval_manager(self) -> ApprovalManager:
        return self._approval_manager

    async def submit_question(self, question: str) -> QueryRecord:
        """Phase 1: Run the LangGraph pipeline until it hits the human_approval interrupt."""
        record = QueryRecord(
            natural_language=question,
            database_type="",
        )

        config = {"configurable": {"thread_id": record.id}}

        # Invoke the graph — it will run discover_schema → generate_sql → validate_sql
        # then pause at human_approval via interrupt()
        await self._graph.ainvoke(
            {"question": question},
            config=config,
        )

        # Read the state after the interrupt
        state = await self._graph.aget_state(config)
        graph_state = state.values

        record.database_type = graph_state.get("dialect", "")
        record.generated_sql = graph_state.get("generated_sql", "")
        record.validation_errors = graph_state.get("validation_errors", [])

        record = await self._approval_manager.submit_for_approval(record)

        logger.info(
            "question_submitted",
            query_id=record.id,
            question=question,
            sql=record.generated_sql,
            validation_errors=record.validation_errors,
        )
        return record

    async def execute_approved(self, query_id: str) -> QueryRecord:
        """Phase 2: Resume the LangGraph pipeline after human approval."""
        record = await self._store.get(query_id)
        if record.approval_status != ApprovalStatus.APPROVED:
            raise ValueError(
                f"Query {query_id} must be approved before execution "
                f"(current status: {record.approval_status.value})"
            )

        config = {"configurable": {"thread_id": query_id}}

        # Resume the graph from the interrupt with approval decision
        resume_value = {"approved": True}
        if record.generated_sql:
            resume_value["modified_sql"] = record.generated_sql

        result = await self._graph.ainvoke(
            Command(resume=resume_value),
            config=config,
        )

        if result.get("error"):
            record.error = result["error"]
            record.approval_status = ApprovalStatus.FAILED
            logger.error("query_execution_failed", query_id=query_id, error=record.error)
        else:
            record.result = result.get("result")
            record.generated_sql = result.get("generated_sql", record.generated_sql)
            record.approval_status = ApprovalStatus.EXECUTED
            record.executed_at = datetime.now(timezone.utc)
            logger.info(
                "query_executed",
                query_id=query_id,
                row_count=len(record.result) if record.result else 0,
            )

        await self._store.save(record)
        return record

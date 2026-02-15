from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

import structlog
from langgraph.types import Command

from text_to_sql.cache.query_cache import QueryCache
from text_to_sql.models.domain import ApprovalStatus, QueryRecord
from text_to_sql.pipeline.approval import ApprovalManager
from text_to_sql.store.base import QueryStore
from text_to_sql.store.session import SessionStore

logger = structlog.get_logger()


class PipelineOrchestrator:
    """Coordinates the full NL -> SQL -> Approval -> Execution pipeline via LangGraph."""

    def __init__(
        self,
        graph: Any,
        query_store: QueryStore,
        session_store: SessionStore | None = None,
        query_cache: QueryCache | None = None,
        schema_hash: str = "",
        database_type: str = "",
    ) -> None:
        self._graph = graph
        self._store = query_store
        self._session_store = session_store
        self._query_cache = query_cache
        self._schema_hash = schema_hash
        self._database_type = database_type
        self._approval_manager = ApprovalManager(query_store)

    @property
    def approval_manager(self) -> ApprovalManager:
        return self._approval_manager

    @property
    def query_store(self) -> QueryStore:
        return self._store

    @property
    def session_store(self) -> SessionStore | None:
        return self._session_store

    @property
    def query_cache(self) -> QueryCache | None:
        return self._query_cache

    async def submit_question(self, question: str) -> QueryRecord:
        """Run the LangGraph pipeline. Safe read-only queries auto-execute; unsafe ones pause for approval."""
        # Check cache for single-shot queries
        if self._query_cache and self._schema_hash:
            cached = await self._query_cache.get(question, self._schema_hash)
            if cached:
                logger.info("cache_hit", question=question[:50])
                record = QueryRecord(
                    natural_language=question,
                    database_type=self._database_type,
                    generated_sql=cached.sql,
                    result=cached.result,
                    answer=cached.answer,
                    approval_status=ApprovalStatus.EXECUTED,
                    executed_at=datetime.now(timezone.utc),
                )
                await self._store.save(record)
                return record

        record = QueryRecord(
            natural_language=question,
            database_type=self._database_type,
        )

        config = {"configurable": {"thread_id": record.id}}

        await self._graph.ainvoke(
            {"messages": [{"role": "user", "content": question}]},
            config=config,
        )

        await self._persist_record(record)

        # Populate cache on successful execution
        if (
            self._query_cache
            and self._schema_hash
            and record.approval_status == ApprovalStatus.EXECUTED
            and record.result is not None
            and record.answer
        ):
            await self._query_cache.set(
                question, self._schema_hash,
                record.generated_sql, record.result, record.answer,
            )

        logger.info(
            "question_submitted",
            query_id=record.id,
            question=question,
            sql=record.generated_sql,
            status=record.approval_status.value,
        )
        return record

    async def submit_question_in_session(
        self, question: str, session_id: str
    ) -> QueryRecord:
        """Run the pipeline within a session context for multi-turn conversations."""
        record = QueryRecord(
            natural_language=question,
            database_type=self._database_type,
            session_id=session_id,
        )

        # Use session_id as thread_id for LangGraph checkpointing — this gives
        # the LLM conversation memory across questions in the same session.
        config = {"configurable": {"thread_id": session_id}}

        await self._graph.ainvoke(
            {"messages": [{"role": "user", "content": question}]},
            config=config,
        )

        await self._persist_record(record)

        # Track query in session
        if self._session_store:
            await self._session_store.update_activity(session_id, record.id)

        logger.info(
            "question_submitted_in_session",
            query_id=record.id,
            session_id=session_id,
            question=question,
            sql=record.generated_sql,
            status=record.approval_status.value,
        )
        return record

    async def stream_question(
        self, question: str, session_id: str
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream pipeline events via SSE for a question in a session."""
        config = {"configurable": {"thread_id": session_id}}

        async for chunk in self._graph.astream(
            {"messages": [{"role": "user", "content": question}]},
            config=config,
            stream_mode="custom",
        ):
            yield chunk

    async def execute_approved(self, query_id: str) -> QueryRecord:
        """Resume the LangGraph pipeline after human approval."""
        record = await self._store.get(query_id)
        if record.approval_status != ApprovalStatus.APPROVED:
            raise ValueError(
                f"Query {query_id} must be approved before execution "
                f"(current status: {record.approval_status.value})"
            )

        # Use session_id as thread_id if available, else query_id
        thread_id = record.session_id or query_id
        config = {"configurable": {"thread_id": thread_id}}

        # Resume the graph from the interrupt with approval decision
        resume_value: dict[str, Any] = {"approved": True}
        if record.generated_sql:
            resume_value["modified_sql"] = record.generated_sql

        await self._graph.ainvoke(
            Command(resume=resume_value),
            config=config,
        )

        # Read final state after graph completes
        state = await self._graph.aget_state(config)
        result = state.values

        if result.get("error"):
            record.error = result["error"]
            record.approval_status = ApprovalStatus.FAILED
            logger.error("query_execution_failed", query_id=query_id, error=record.error)
        else:
            record.result = result.get("result")
            record.answer = result.get("answer")
            record.generated_sql = result.get("generated_sql") or record.generated_sql
            record.approval_status = ApprovalStatus.EXECUTED
            record.executed_at = datetime.now(timezone.utc)
            logger.info(
                "query_executed",
                query_id=query_id,
                row_count=len(record.result) if record.result else 0,
            )

        await self._store.save(record)
        return record

    async def _persist_record(self, record: QueryRecord) -> None:
        """Save the record — either directly or via approval manager for pending records."""
        state = await self._graph.aget_state(
            {"configurable": {"thread_id": record.session_id or record.id}}
        )
        graph_state = state.values

        record.generated_sql = graph_state.get("generated_sql") or ""
        record.validation_errors = graph_state.get("validation_errors", [])
        record.query_type = graph_state.get("query_type", "simple")
        if record.query_type == "analytical":
            record.analysis_plan = graph_state.get("analysis_plan")
            record.analysis_steps = graph_state.get("plan_results")

        if not state.next:
            if graph_state.get("error"):
                record.error = graph_state["error"]
                record.approval_status = ApprovalStatus.FAILED
            else:
                record.result = graph_state.get("result")
                record.answer = graph_state.get("answer")
                record.approval_status = ApprovalStatus.EXECUTED
                record.executed_at = datetime.now(timezone.utc)
            await self._store.save(record)
        else:
            # Graph paused at human_approval interrupt
            record = await self._approval_manager.submit_for_approval(record)

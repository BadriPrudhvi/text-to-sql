from __future__ import annotations

from typing import Any, TypedDict

import structlog
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from text_to_sql.db.base import DatabaseBackend
from text_to_sql.llm.sql_generator import SQLGenerator
from text_to_sql.schema.cache import SchemaCache
from text_to_sql.schema.discovery import SchemaDiscoveryService

logger = structlog.get_logger()


class PipelineState(TypedDict, total=False):
    """State flowing through the text-to-SQL LangGraph pipeline."""

    question: str
    dialect: str
    schema_context: str
    generated_sql: str
    validation_errors: list[str]
    approved: bool | None
    modified_sql: str | None
    result: list[dict[str, Any]] | None
    error: str | None


def build_pipeline_graph(
    db_backend: DatabaseBackend,
    schema_cache: SchemaCache,
    chat_model: BaseChatModel,
) -> StateGraph:
    """Build the LangGraph StateGraph for text-to-SQL pipeline.

    Flow: discover_schema → generate_sql → validate_sql → human_approval → execute_sql
    """
    schema_service = SchemaDiscoveryService(db_backend, schema_cache)
    sql_generator = SQLGenerator(chat_model)

    # --- Node functions ---

    async def discover_schema(state: PipelineState) -> PipelineState:
        """Discover database schema and format as context for the LLM."""
        schema = await schema_service.get_schema()
        context = schema_service.schema_to_prompt_context(schema)
        logger.info("graph_schema_discovered", table_count=len(schema.tables))
        return {
            "schema_context": context,
            "dialect": db_backend.backend_type,
        }

    async def generate_sql(state: PipelineState) -> PipelineState:
        """Generate SQL from the natural language question using the LLM."""
        sql = await sql_generator.generate(
            question=state["question"],
            schema_context=state["schema_context"],
            dialect=state["dialect"],
        )
        logger.info("graph_sql_generated", sql=sql)
        return {"generated_sql": sql}

    async def validate_sql(state: PipelineState) -> PipelineState:
        """Validate the generated SQL against the database."""
        errors = await db_backend.validate_sql(state["generated_sql"])
        if errors:
            logger.warning("graph_sql_validation_errors", errors=errors)
        return {"validation_errors": errors}

    async def human_approval(state: PipelineState) -> PipelineState:
        """Pause execution and wait for human approval via interrupt()."""
        decision = interrupt(
            {
                "generated_sql": state["generated_sql"],
                "validation_errors": state.get("validation_errors", []),
                "message": "Review the generated SQL. Resume with {'approved': true/false, 'modified_sql': '...'}",
            }
        )
        approved = decision.get("approved", False) if isinstance(decision, dict) else bool(decision)
        modified_sql = decision.get("modified_sql") if isinstance(decision, dict) else None

        if modified_sql:
            return {"approved": approved, "modified_sql": modified_sql, "generated_sql": modified_sql}
        return {"approved": approved}

    async def execute_sql(state: PipelineState) -> PipelineState:
        """Execute the approved SQL query."""
        try:
            result = await db_backend.execute_sql(state["generated_sql"])
            logger.info("graph_sql_executed", row_count=len(result))
            return {"result": result}
        except Exception as e:
            logger.error("graph_sql_execution_failed", error=str(e))
            return {"error": str(e)}

    # --- Route function ---

    def route_after_approval(state: PipelineState) -> str:
        """Route based on human approval decision."""
        if state.get("approved"):
            return "execute_sql"
        return END

    # --- Build graph ---

    builder = StateGraph(PipelineState)

    builder.add_node("discover_schema", discover_schema)
    builder.add_node("generate_sql", generate_sql)
    builder.add_node("validate_sql", validate_sql)
    builder.add_node("human_approval", human_approval)
    builder.add_node("execute_sql", execute_sql)

    builder.add_edge(START, "discover_schema")
    builder.add_edge("discover_schema", "generate_sql")
    builder.add_edge("generate_sql", "validate_sql")
    builder.add_edge("validate_sql", "human_approval")
    builder.add_conditional_edges("human_approval", route_after_approval, ["execute_sql", END])
    builder.add_edge("execute_sql", END)

    return builder


def compile_pipeline(
    db_backend: DatabaseBackend,
    schema_cache: SchemaCache,
    chat_model: BaseChatModel,
    checkpointer: MemorySaver | None = None,
):
    """Build and compile the pipeline graph with optional checkpointer."""
    builder = build_pipeline_graph(db_backend, schema_cache, chat_model)
    if checkpointer is None:
        checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)

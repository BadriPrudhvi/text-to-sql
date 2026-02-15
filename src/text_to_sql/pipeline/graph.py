from __future__ import annotations

import json
from typing import Any

import structlog
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.types import interrupt

from text_to_sql.db.base import DatabaseBackend
from text_to_sql.llm.prompts import FEW_SHOT_EXAMPLES, SQL_AGENT_SYSTEM_PROMPT
from text_to_sql.pipeline.agents import extract_user_question
from text_to_sql.pipeline.tools import create_run_query_tool
from text_to_sql.schema.cache import SchemaCache
from text_to_sql.schema.discovery import SchemaDiscoveryService

logger = structlog.get_logger()


class SQLAgentState(MessagesState):
    """Extends MessagesState with structured fields for API responses."""

    generated_sql: str | None = None
    validation_errors: list[str] = []
    result: list[dict[str, Any]] | None = None
    answer: str | None = None
    error: str | None = None
    correction_attempts: int = 0

    # Analytical query support
    query_type: str = "simple"
    analysis_plan: list[dict[str, str]] | None = None
    plan_results: list[dict[str, Any]] | None = None
    current_step: int = 0
    synthesis_attempts: int = 0


def build_pipeline_graph(
    db_backend: DatabaseBackend,
    schema_cache: SchemaCache,
    chat_model: BaseChatModel,
    include_tables: list[str] | None = None,
    exclude_tables: list[str] | None = None,
    context_max_tokens: int = 16000,
    context_schema_budget_pct: float = 0.6,
    context_history_max_messages: int = 10,
    schema_selection_mode: str = "none",
    schema_max_selected_tables: int = 15,
    max_correction_attempts: int = 2,
    llm_retry_attempts: int = 3,
    llm_retry_min_wait: int = 2,
    llm_retry_max_wait: int = 10,
    db_query_timeout_seconds: float | None = None,
    analytical_max_plan_steps: int = 7,
    analytical_max_synthesis_attempts: int = 1,
) -> StateGraph:
    """Build the LangGraph StateGraph for text-to-SQL agent pipeline."""
    from text_to_sql.llm.retry import create_invoke_with_retry
    from text_to_sql.pipeline.agents.analyst import create_synthesize_analysis_node
    from text_to_sql.pipeline.agents.analysis_validator import (
        create_validate_analysis_node,
    )
    from text_to_sql.pipeline.agents.classifier import create_classify_query_node
    from text_to_sql.pipeline.agents.executor import create_execute_plan_step_node
    from text_to_sql.pipeline.agents.planner import create_plan_analysis_node

    schema_service = SchemaDiscoveryService(
        db_backend, schema_cache,
        include_tables=include_tables,
        exclude_tables=exclude_tables,
    )
    schema_budget = int(context_max_tokens * context_schema_budget_pct)
    run_query_tool = create_run_query_tool(db_backend)
    model_with_tools = chat_model.bind_tools([run_query_tool])
    invoke_with_retry = create_invoke_with_retry(
        max_attempts=llm_retry_attempts,
        min_wait=llm_retry_min_wait,
        max_wait=llm_retry_max_wait,
    )

    dialect = db_backend.backend_type

    async def discover_schema(state: SQLAgentState) -> dict:
        """Discover database schema and inject as system message."""
        from text_to_sql.schema.selector import TableSelector

        writer = get_stream_writer()
        writer({"event": "schema_discovery_started"})
        schema = await schema_service.get_schema()

        # Dynamic schema selection
        tables = schema.tables
        if schema_selection_mode != "none" and tables:
            selector = TableSelector()
            user_question = extract_user_question(state["messages"])

            if user_question:
                if schema_selection_mode == "llm":
                    tables = await selector.select_by_llm(
                        user_question, tables, chat_model,
                        max_tables=schema_max_selected_tables,
                    )
                else:
                    tables = selector.select_by_keywords(
                        user_question, tables,
                        max_tables=schema_max_selected_tables,
                    )
                from text_to_sql.models.domain import SchemaInfo as _SI
                schema = _SI(tables=tables, discovered_at=schema.discovered_at)

        # Budgeted schema rendering
        context = schema_service.schema_to_prompt_context_budgeted(schema, schema_budget)
        logger.info("graph_schema_discovered", table_count=len(schema.tables))
        writer({"event": "schema_discovered", "table_count": len(schema.tables)})

        system_msg = SystemMessage(
            content=SQL_AGENT_SYSTEM_PROMPT.format(
                dialect=dialect,
                schema_context=context,
                top_k=5,
                few_shot_examples=FEW_SHOT_EXAMPLES,
            )
        )
        return {"messages": [system_msg]}

    async def generate_query(state: SQLAgentState) -> dict:
        """Invoke the LLM with tools. It either makes a tool call (SQL) or returns text (answer)."""
        writer = get_stream_writer()
        writer({"event": "llm_generation_started"})
        messages = state["messages"]
        # Truncate history to keep context manageable
        if len(messages) > context_history_max_messages + 1:
            messages = [messages[0]] + messages[-(context_history_max_messages):]
        response = await invoke_with_retry(model_with_tools, messages)

        updates: dict[str, Any] = {"messages": [response]}

        if isinstance(response, AIMessage) and response.tool_calls:
            sql = response.tool_calls[0]["args"].get("query", "")
            updates["generated_sql"] = sql
            logger.info("graph_sql_generated", sql=sql)
            writer({"event": "sql_generated", "sql": sql})
        elif isinstance(response, AIMessage) and response.content:
            updates["answer"] = str(response.content)
            logger.info("graph_answer_generated", answer=updates["answer"][:100])
            writer({"event": "answer_generated", "answer": updates["answer"]})

        return updates

    async def check_query(state: SQLAgentState) -> dict:
        """Validate the SQL from the last tool call."""
        writer = get_stream_writer()
        sql = state.get("generated_sql", "")
        errors = await db_backend.validate_sql(sql)
        if errors:
            logger.warning("graph_sql_validation_errors", errors=errors)
            writer({"event": "validation_failed", "errors": errors})
        else:
            writer({"event": "validation_passed"})
        return {"validation_errors": errors}

    async def human_approval(state: SQLAgentState) -> dict:
        """Pause execution and wait for human approval via interrupt()."""
        decision = interrupt(
            {
                "generated_sql": state.get("generated_sql", ""),
                "validation_errors": state.get("validation_errors", []),
                "message": "Review the generated SQL. Resume with {'approved': true/false, 'modified_sql': '...'}",
            }
        )
        approved = decision.get("approved", False) if isinstance(decision, dict) else bool(decision)
        modified_sql = decision.get("modified_sql") if isinstance(decision, dict) else None

        if not approved:
            return {"error": "Query rejected by user."}

        if modified_sql:
            return {"generated_sql": modified_sql}
        return {}

    async def run_query(state: SQLAgentState) -> dict:
        """Execute the SQL directly via db_backend and append a ToolMessage for the ReAct loop."""
        writer = get_stream_writer()
        sql = state.get("generated_sql", "")
        writer({"event": "query_execution_started", "sql": sql})

        tool_call_id = "unknown"
        for msg in reversed(state["messages"]):
            if isinstance(msg, AIMessage) and msg.tool_calls:
                tool_call_id = msg.tool_calls[0]["id"]
                break

        try:
            result = await db_backend.execute_sql(sql, timeout_seconds=db_query_timeout_seconds)
            result_json = json.dumps(result, default=str)
            logger.info("graph_sql_executed", row_count=len(result))
            writer({"event": "query_executed", "row_count": len(result)})
            tool_msg = ToolMessage(content=result_json, tool_call_id=tool_call_id)
            return {"messages": [tool_msg], "result": result}
        except Exception as e:
            logger.error("graph_sql_execution_failed", error=str(e))
            writer({"event": "query_execution_failed", "error": str(e)})
            error_msg = ToolMessage(content=f"Error: {e}", tool_call_id=tool_call_id)
            return {"messages": [error_msg], "error": "Query execution failed."}

    async def validate_result(state: SQLAgentState) -> dict:
        """Validate query results and feed warnings back to LLM for self-correction."""
        from text_to_sql.pipeline.validators import ResultValidator

        writer = get_stream_writer()

        if state.get("correction_attempts", 0) >= max_correction_attempts:
            return {}

        validator = ResultValidator()
        user_question = extract_user_question(state["messages"])

        warnings = validator.validate(
            state.get("generated_sql") or "",
            state.get("result"),
            user_question,
        )
        if not warnings:
            return {}

        logger.info("graph_result_validation_warnings", warnings=warnings)
        writer({"event": "self_correction_triggered", "warnings": warnings})

        tool_call_id = "unknown"
        for msg in reversed(state["messages"]):
            if isinstance(msg, AIMessage) and msg.tool_calls:
                tool_call_id = msg.tool_calls[0]["id"]
                break

        tool_msg = ToolMessage(
            content=f"Warning: {'; '.join(warnings)}. Please revise the query.",
            tool_call_id=tool_call_id,
        )
        return {
            "messages": [tool_msg],
            "correction_attempts": state.get("correction_attempts", 0) + 1,
        }

    # Create analytical agent nodes
    classify_query = create_classify_query_node(chat_model, invoke_with_retry)
    plan_analysis = create_plan_analysis_node(
        chat_model, invoke_with_retry, analytical_max_plan_steps
    )
    execute_plan_step = create_execute_plan_step_node(
        chat_model, db_backend, invoke_with_retry, dialect, db_query_timeout_seconds
    )
    synthesize_analysis = create_synthesize_analysis_node(
        chat_model, invoke_with_retry
    )
    validate_analysis = create_validate_analysis_node(
        analytical_max_synthesis_attempts
    )

    # Routing functions
    def should_continue(state: SQLAgentState) -> str:
        """Route after generate_query: tool calls -> check_query, text -> END."""
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "check_query"
        return END

    def route_after_check(state: SQLAgentState) -> str:
        if state.get("validation_errors"):
            return "human_approval"
        return "run_query"

    def route_after_approval(state: SQLAgentState) -> str:
        if state.get("error"):
            return END
        return "run_query"

    def route_after_classification(state: SQLAgentState) -> str:
        if state.get("query_type") == "analytical":
            return "plan_analysis"
        return "generate_query"

    def route_after_step(state: SQLAgentState) -> str:
        current_step = state.get("current_step", 0)
        plan = state.get("analysis_plan") or []
        if current_step < len(plan):
            return "execute_plan_step"
        return "synthesize_analysis"

    def route_after_analysis_validation(state: SQLAgentState) -> str:
        last = state["messages"][-1]
        # If the validator added a HumanMessage with revision guidance, re-synthesize
        if hasattr(last, "content") and not isinstance(
            last, (AIMessage, SystemMessage, ToolMessage)
        ):
            content = str(last.content)
            if content.startswith("Please revise the analysis"):
                return "synthesize_analysis"
        return END

    builder = StateGraph(SQLAgentState)

    # Existing nodes
    builder.add_node("discover_schema", discover_schema)
    builder.add_node("generate_query", generate_query)
    builder.add_node("check_query", check_query)
    builder.add_node("human_approval", human_approval)
    builder.add_node("run_query", run_query)
    builder.add_node("validate_result", validate_result)

    # Analytical agent nodes
    builder.add_node("classify_query", classify_query)
    builder.add_node("plan_analysis", plan_analysis)
    builder.add_node("execute_plan_step", execute_plan_step)
    builder.add_node("synthesize_analysis", synthesize_analysis)
    builder.add_node("validate_analysis", validate_analysis)

    # Edges: discover_schema → classify_query → (simple | analytical)
    builder.add_edge(START, "discover_schema")
    builder.add_edge("discover_schema", "classify_query")
    builder.add_conditional_edges(
        "classify_query", route_after_classification,
        ["generate_query", "plan_analysis"],
    )

    # Simple path (unchanged)
    builder.add_conditional_edges("generate_query", should_continue, ["check_query", END])
    builder.add_conditional_edges("check_query", route_after_check, ["run_query", "human_approval"])
    builder.add_conditional_edges("human_approval", route_after_approval, ["run_query", END])
    builder.add_edge("run_query", "validate_result")
    builder.add_edge("validate_result", "generate_query")

    # Analytical path
    builder.add_edge("plan_analysis", "execute_plan_step")
    builder.add_conditional_edges(
        "execute_plan_step", route_after_step,
        ["execute_plan_step", "synthesize_analysis"],
    )
    builder.add_edge("synthesize_analysis", "validate_analysis")
    builder.add_conditional_edges(
        "validate_analysis", route_after_analysis_validation,
        ["synthesize_analysis", END],
    )

    return builder


def compile_pipeline(
    db_backend: DatabaseBackend,
    schema_cache: SchemaCache,
    chat_model: BaseChatModel,
    checkpointer: BaseCheckpointSaver | None = None,
    include_tables: list[str] | None = None,
    exclude_tables: list[str] | None = None,
    context_max_tokens: int = 16000,
    context_schema_budget_pct: float = 0.6,
    context_history_max_messages: int = 10,
    schema_selection_mode: str = "none",
    schema_max_selected_tables: int = 15,
    max_correction_attempts: int = 2,
    llm_retry_attempts: int = 3,
    llm_retry_min_wait: int = 2,
    llm_retry_max_wait: int = 10,
    db_query_timeout_seconds: float | None = None,
    analytical_max_plan_steps: int = 7,
    analytical_max_synthesis_attempts: int = 1,
):
    """Build and compile the pipeline graph with optional checkpointer."""
    builder = build_pipeline_graph(
        db_backend, schema_cache, chat_model,
        include_tables=include_tables,
        exclude_tables=exclude_tables,
        context_max_tokens=context_max_tokens,
        context_schema_budget_pct=context_schema_budget_pct,
        context_history_max_messages=context_history_max_messages,
        schema_selection_mode=schema_selection_mode,
        schema_max_selected_tables=schema_max_selected_tables,
        max_correction_attempts=max_correction_attempts,
        llm_retry_attempts=llm_retry_attempts,
        llm_retry_min_wait=llm_retry_min_wait,
        llm_retry_max_wait=llm_retry_max_wait,
        db_query_timeout_seconds=db_query_timeout_seconds,
        analytical_max_plan_steps=analytical_max_plan_steps,
        analytical_max_synthesis_attempts=analytical_max_synthesis_attempts,
    )
    if checkpointer is None:
        checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)

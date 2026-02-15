from __future__ import annotations

import json
from typing import Any

import structlog
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.types import interrupt

from text_to_sql.db.base import DatabaseBackend
from text_to_sql.llm.prompts import FEW_SHOT_EXAMPLES, SQL_AGENT_SYSTEM_PROMPT
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
) -> StateGraph:
    """Build the LangGraph StateGraph for text-to-SQL agent pipeline."""
    schema_service = SchemaDiscoveryService(
        db_backend, schema_cache,
        include_tables=include_tables,
        exclude_tables=exclude_tables,
    )
    schema_budget = int(context_max_tokens * context_schema_budget_pct)
    run_query_tool = create_run_query_tool(db_backend)
    model_with_tools = chat_model.bind_tools([run_query_tool])

    async def discover_schema(state: SQLAgentState) -> dict:
        """Discover database schema and inject as system message."""
        from text_to_sql.schema.selector import TableSelector

        schema = await schema_service.get_schema()

        # Phase 3: Dynamic schema selection
        tables = schema.tables
        if schema_selection_mode != "none" and tables:
            selector = TableSelector()
            user_question = ""
            for msg in reversed(state["messages"]):
                if hasattr(msg, "content") and not isinstance(msg, (AIMessage, SystemMessage, ToolMessage)):
                    user_question = str(msg.content)
                    break

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

        # Phase 2: Budgeted schema rendering
        context = schema_service.schema_to_prompt_context_budgeted(schema, schema_budget)
        dialect = db_backend.backend_type
        logger.info("graph_schema_discovered", table_count=len(schema.tables))

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
        messages = state["messages"]
        # Phase 2D: Truncate history to keep context manageable
        if len(messages) > context_history_max_messages + 1:
            # Keep system message (index 0) + last N messages
            messages = [messages[0]] + messages[-(context_history_max_messages):]
        response = await model_with_tools.ainvoke(messages)

        updates: dict[str, Any] = {"messages": [response]}

        if isinstance(response, AIMessage) and response.tool_calls:
            sql = response.tool_calls[0]["args"].get("query", "")
            updates["generated_sql"] = sql
            logger.info("graph_sql_generated", sql=sql)
        elif isinstance(response, AIMessage) and response.content:
            updates["answer"] = str(response.content)
            logger.info("graph_answer_generated", answer=updates["answer"][:100])

        return updates

    async def check_query(state: SQLAgentState) -> dict:
        """Validate the SQL from the last tool call."""
        sql = state.get("generated_sql", "")
        errors = await db_backend.validate_sql(sql)
        if errors:
            logger.warning("graph_sql_validation_errors", errors=errors)
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
        sql = state.get("generated_sql", "")

        # Find the tool_call_id from the last AIMessage to create a proper ToolMessage
        tool_call_id = "unknown"
        for msg in reversed(state["messages"]):
            if isinstance(msg, AIMessage) and msg.tool_calls:
                tool_call_id = msg.tool_calls[0]["id"]
                break

        try:
            result = await db_backend.execute_sql(sql)
            result_json = json.dumps(result, default=str)
            logger.info("graph_sql_executed", row_count=len(result))
            tool_msg = ToolMessage(content=result_json, tool_call_id=tool_call_id)
            return {"messages": [tool_msg], "result": result}
        except Exception as e:
            logger.error("graph_sql_execution_failed", error=str(e))
            error_msg = ToolMessage(content=f"Error: {e}", tool_call_id=tool_call_id)
            return {"messages": [error_msg], "error": "Query execution failed."}

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

    builder = StateGraph(SQLAgentState)

    builder.add_node("discover_schema", discover_schema)
    builder.add_node("generate_query", generate_query)
    builder.add_node("check_query", check_query)
    builder.add_node("human_approval", human_approval)
    builder.add_node("run_query", run_query)

    builder.add_edge(START, "discover_schema")
    builder.add_edge("discover_schema", "generate_query")
    builder.add_conditional_edges("generate_query", should_continue, ["check_query", END])
    builder.add_conditional_edges("check_query", route_after_check, ["run_query", "human_approval"])
    builder.add_conditional_edges("human_approval", route_after_approval, ["run_query", END])
    builder.add_edge("run_query", "generate_query")  # ReAct loop

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
    )
    if checkpointer is None:
        checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)

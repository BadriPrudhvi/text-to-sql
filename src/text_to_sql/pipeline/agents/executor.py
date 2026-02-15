"""Plan step executor agent — generates and runs SQL for each analysis step."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import structlog
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.config import get_stream_writer

from text_to_sql.db.base import DatabaseBackend
from text_to_sql.pipeline.agents.prompts import STEP_SQL_PROMPT

logger = structlog.get_logger()


def create_execute_plan_step_node(
    chat_model: BaseChatModel,
    db_backend: DatabaseBackend,
    invoke_with_retry: Callable,
    dialect: str,
    db_query_timeout_seconds: float | None = None,
) -> Callable[..., Any]:
    """Create the plan step execution node."""

    async def execute_plan_step(state: dict) -> dict:
        writer = get_stream_writer()
        current_step = state.get("current_step", 0)
        plan = state.get("analysis_plan", [])
        plan_results = list(state.get("plan_results") or [])

        step = plan[current_step]
        step_desc = step["description"]
        writer({
            "event": "plan_step_started",
            "step_index": current_step,
            "description": step_desc,
        })

        # Extract schema context from SystemMessage
        schema_context = ""
        for msg in state["messages"]:
            if isinstance(msg, SystemMessage):
                schema_context = str(msg.content)
                break

        # Build previous results context
        previous_results_context = ""
        if plan_results:
            parts = []
            for i, r in enumerate(plan_results):
                status = "Success" if not r.get("error") else f"Failed: {r['error']}"
                result_preview = ""
                if r.get("result"):
                    result_preview = json.dumps(r["result"][:5], default=str)
                parts.append(
                    f"Step {i + 1} ({r['description']}): {status}\n"
                    f"  SQL: {r.get('sql', 'N/A')}\n"
                    f"  Result preview: {result_preview}"
                )
            previous_results_context = (
                "Previous step results:\n" + "\n".join(parts)
            )

        step_result: dict[str, Any] = {
            "description": step_desc,
            "sql": None,
            "result": None,
            "error": None,
        }

        try:
            # Generate SQL for this step
            prompt = STEP_SQL_PROMPT.format(
                dialect=dialect,
                step_description=step_desc,
                sql_hint=step["sql_hint"],
                schema_context=schema_context,
                previous_results_context=previous_results_context,
            )
            response = await invoke_with_retry(
                chat_model, [HumanMessage(content=prompt)]
            )
            sql = str(response.content).strip()
            # Strip markdown code fences if present
            if sql.startswith("```"):
                lines = sql.split("\n")
                sql = "\n".join(
                    line for line in lines
                    if not line.startswith("```")
                ).strip()

            step_result["sql"] = sql
            writer({
                "event": "plan_step_sql_generated",
                "step_index": current_step,
                "sql": sql,
            })

            # Validate SQL
            errors = await db_backend.validate_sql(sql)
            if errors:
                step_result["error"] = f"Validation failed: {'; '.join(errors)}"
                writer({
                    "event": "plan_step_failed",
                    "step_index": current_step,
                    "error": step_result["error"],
                })
            else:
                # Execute SQL
                result = await db_backend.execute_sql(
                    sql, timeout_seconds=db_query_timeout_seconds
                )
                step_result["result"] = result
                logger.info(
                    "plan_step_executed",
                    step_index=current_step,
                    row_count=len(result),
                )
                writer({
                    "event": "plan_step_executed",
                    "step_index": current_step,
                    "row_count": len(result),
                })
        except Exception as e:
            step_result["error"] = str(e)
            logger.warning(
                "plan_step_failed",
                step_index=current_step,
                error=str(e),
            )
            writer({
                "event": "plan_step_failed",
                "step_index": current_step,
                "error": str(e),
            })

        plan_results.append(step_result)
        return {
            "plan_results": plan_results,
            "current_step": current_step + 1,
        }

    return execute_plan_step

"""Plan step executor agent — generates and runs SQL for each analysis step."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import structlog
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.config import get_stream_writer

from text_to_sql.db.base import DatabaseBackend, clean_llm_sql
from text_to_sql.pipeline.agents import extract_text
from text_to_sql.pipeline.agents.models import StepSQLResult
from text_to_sql.pipeline.agents.prompts import STEP_SQL_PROMPT

logger = structlog.get_logger()


_MAX_STEP_CORRECTION_ATTEMPTS = 2

STEP_SQL_CORRECTION_PROMPT = """\
The SQL you generated for this analysis step failed validation.

Original step description: {step_description}
SQL hint: {sql_hint}

Your SQL:
{sql}

Error: {error}

Fix the SQL and return ONLY the corrected query. Common fixes:
- Fully qualify column names with table aliases when joining multiple tables
- Use correct syntax for the {dialect} dialect
- Ensure all referenced tables and columns exist in the schema"""


def create_execute_plan_step_node(
    chat_model: BaseChatModel,
    db_backend: DatabaseBackend,
    invoke_with_retry: Callable,
    dialect: str,
    db_query_timeout_seconds: float | None = None,
) -> Callable[..., Any]:
    """Create the plan step execution node."""
    structured_model = chat_model.with_structured_output(StepSQLResult)

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
                schema_context = extract_text(msg.content)
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
            messages = [HumanMessage(content=prompt)]

            # Layer 1: Try structured output (primary defense)
            try:
                result = await invoke_with_retry(structured_model, messages)
                if isinstance(result, StepSQLResult):
                    sql = result.sql.strip()
                else:
                    # Structured output returned unexpected type — fall back
                    sql = extract_text(result.content).strip() if hasattr(result, "content") else str(result).strip()
            except Exception:
                # Layer 2: Fall back to raw text
                logger.debug("structured_output_fallback", step_index=current_step)
                response = await invoke_with_retry(chat_model, messages)
                sql = extract_text(response.content).strip()

            # Defense in depth: clean any residual LLM explanation text
            sql = clean_llm_sql(sql)

            step_result["sql"] = sql
            writer({
                "event": "plan_step_sql_generated",
                "step_index": current_step,
                "sql": sql,
            })

            # Validate and execute with self-correction
            for attempt in range(_MAX_STEP_CORRECTION_ATTEMPTS + 1):
                errors = await db_backend.validate_sql(sql)
                if not errors:
                    # Execute SQL
                    result = await db_backend.execute_sql(
                        sql, timeout_seconds=db_query_timeout_seconds
                    )
                    step_result["sql"] = sql
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
                    break

                # Out of retries — record the error
                if attempt == _MAX_STEP_CORRECTION_ATTEMPTS:
                    step_result["error"] = f"Validation failed: {'; '.join(errors)}"
                    writer({
                        "event": "plan_step_failed",
                        "step_index": current_step,
                        "error": step_result["error"],
                    })
                    break

                # Self-correct: feed error back to LLM
                logger.info(
                    "plan_step_correcting",
                    step_index=current_step,
                    attempt=attempt + 1,
                    error="; ".join(errors),
                )
                writer({
                    "event": "plan_step_correcting",
                    "step_index": current_step,
                    "attempt": attempt + 1,
                })
                correction_prompt = STEP_SQL_CORRECTION_PROMPT.format(
                    step_description=step_desc,
                    sql_hint=step["sql_hint"],
                    sql=sql,
                    error="; ".join(errors),
                    dialect=dialect,
                )
                correction_messages = [HumanMessage(content=correction_prompt)]
                try:
                    correction_result = await invoke_with_retry(structured_model, correction_messages)
                    if isinstance(correction_result, StepSQLResult):
                        sql = clean_llm_sql(correction_result.sql.strip())
                    else:
                        sql = clean_llm_sql(extract_text(correction_result.content).strip() if hasattr(correction_result, "content") else str(correction_result).strip())
                except Exception:
                    response = await invoke_with_retry(chat_model, correction_messages)
                    sql = clean_llm_sql(extract_text(response.content).strip())
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

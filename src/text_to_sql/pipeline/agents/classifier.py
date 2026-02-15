"""Query classifier agent — routes queries as simple or analytical."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import structlog
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langgraph.config import get_stream_writer

from text_to_sql.pipeline.agents import extract_user_question
from text_to_sql.pipeline.agents.models import QueryClassification
from text_to_sql.pipeline.agents.prompts import CLASSIFICATION_PROMPT

logger = structlog.get_logger()


def create_classify_query_node(
    chat_model: BaseChatModel,
    invoke_with_retry: Callable,
) -> Callable[..., Any]:
    """Create the query classification node."""
    structured_model = chat_model.with_structured_output(QueryClassification)

    async def classify_query(state: dict) -> dict:
        writer = get_stream_writer()
        writer({"event": "classifying_query"})

        question = extract_user_question(state["messages"])
        if not question:
            logger.warning("classify_query_no_question")
            writer({"event": "query_classified", "query_type": "simple"})
            return {"query_type": "simple"}

        try:
            prompt = CLASSIFICATION_PROMPT.format(question=question)
            result = await invoke_with_retry(
                structured_model, [HumanMessage(content=prompt)]
            )
            query_type = result.query_type
            logger.info(
                "query_classified",
                query_type=query_type,
                reasoning=result.reasoning,
            )
            writer({"event": "query_classified", "query_type": query_type})
            return {"query_type": query_type}
        except Exception:
            logger.warning("classify_query_llm_failed", exc_info=True)
            writer({"event": "query_classified", "query_type": "simple"})
            return {"query_type": "simple"}

    return classify_query

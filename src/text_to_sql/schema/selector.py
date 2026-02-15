from __future__ import annotations

import json
import re

import structlog
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from text_to_sql.models.domain import TableInfo

logger = structlog.get_logger()


def _tokenize(text: str) -> set[str]:
    """Split text into lowercase tokens, handling underscores and camelCase."""
    # Split camelCase: "orderItems" -> "order Items"
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    # Split on non-alphanumeric (underscores, spaces, etc.)
    parts = re.split(r"[^a-zA-Z0-9]+", text)
    return {p.lower() for p in parts if p}


class TableSelector:
    """Select relevant tables for a user question."""

    def select_by_keywords(
        self,
        question: str,
        tables: list[TableInfo],
        max_tables: int = 15,
    ) -> list[TableInfo]:
        """Score tables by keyword overlap with the question.

        Tokenizes question, table names, column names, and descriptions.
        Returns top-scoring tables up to max_tables. Falls back to all
        tables (capped) if no matches found.
        """
        question_tokens = _tokenize(question)
        if not question_tokens:
            return tables[:max_tables]

        scored: list[tuple[float, TableInfo]] = []
        for table in tables:
            table_tokens = _tokenize(table.table_name)
            if table.description:
                table_tokens |= _tokenize(table.description)
            for col in table.columns:
                table_tokens |= _tokenize(col.name)
                if col.description:
                    table_tokens |= _tokenize(col.description)

            overlap = len(question_tokens & table_tokens)
            if overlap > 0:
                scored.append((overlap, table))

        if not scored:
            # No matches — fall back to all tables capped at max
            return tables[:max_tables]

        scored.sort(key=lambda x: x[0], reverse=True)
        return [t for _, t in scored[:max_tables]]

    async def select_by_llm(
        self,
        question: str,
        tables: list[TableInfo],
        chat_model: BaseChatModel,
        max_tables: int = 15,
    ) -> list[TableInfo]:
        """Use an LLM to select relevant tables.

        Sends a compact table summary and asks for a JSON array of table names.
        Falls back to keyword matching on parse failure.
        """
        table_summaries = []
        for t in tables:
            cols = ", ".join(c.name for c in t.columns)
            desc = f" -- {t.description}" if t.description else ""
            table_summaries.append(f"- {t.table_name}{desc}: [{cols}]")

        prompt = (
            f"Given this user question: \"{question}\"\n\n"
            f"Which of these database tables are relevant? "
            f"Return ONLY a JSON array of table names (max {max_tables}).\n\n"
            + "\n".join(table_summaries)
        )

        try:
            response = await chat_model.ainvoke([
                SystemMessage(content="You select relevant database tables. Return only a JSON array of table names."),
                HumanMessage(content=prompt),
            ])
            content = str(response.content)
            # Extract JSON array from response
            match = re.search(r"\[.*?\]", content, re.DOTALL)
            if not match:
                raise ValueError("No JSON array found in response")

            selected_names: list[str] = json.loads(match.group())
            name_set = set(selected_names)
            selected = [t for t in tables if t.table_name in name_set]

            if selected:
                logger.info("schema_llm_selection", selected=len(selected), total=len(tables))
                return selected[:max_tables]
        except Exception:
            logger.warning("schema_llm_selection_fallback", exc_info=True)

        # Fallback to keyword matching
        return self.select_by_keywords(question, tables, max_tables)

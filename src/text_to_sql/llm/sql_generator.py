from __future__ import annotations

import re

import structlog
from langchain_core.language_models.chat_models import BaseChatModel

from text_to_sql.llm.prompts import SQL_GENERATION_PROMPT

logger = structlog.get_logger()

_CODE_FENCE_RE = re.compile(r"^```(?:sql)?\s*\n?(.*?)\n?```$", re.DOTALL | re.IGNORECASE)


class SQLGenerator:
    """Generates SQL from natural language using LangChain ChatModel with fallbacks."""

    def __init__(self, chat_model: BaseChatModel) -> None:
        self._chain = SQL_GENERATION_PROMPT | chat_model

    async def generate(
        self,
        question: str,
        schema_context: str,
        dialect: str,
    ) -> str:
        response = await self._chain.ainvoke(
            {
                "question": question,
                "schema_context": schema_context,
                "dialect": dialect,
            }
        )

        raw = response.content.strip()
        sql = self._strip_code_fences(raw)

        logger.info("sql_generated", question=question, sql=sql)
        return sql

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        stripped = text.strip()
        match = _CODE_FENCE_RE.match(stripped)
        return match.group(1).strip() if match else stripped

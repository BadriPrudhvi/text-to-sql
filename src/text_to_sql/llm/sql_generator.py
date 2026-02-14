from __future__ import annotations

import re

import structlog
from litellm import Router

from text_to_sql.config import Settings
from text_to_sql.llm.prompts import build_sql_generation_prompt

logger = structlog.get_logger()

_CODE_FENCE_RE = re.compile(r"^```(?:sql)?\s*\n?(.*?)\n?```$", re.DOTALL | re.IGNORECASE)


class SQLGenerator:
    """Generates SQL from natural language using LiteLLM Router."""

    def __init__(self, router: Router, settings: Settings) -> None:
        self._router = router
        self._settings = settings

    async def generate(
        self,
        question: str,
        schema_context: str,
        dialect: str,
    ) -> str:
        messages = build_sql_generation_prompt(question, schema_context, dialect)

        response = await self._router.acompletion(
            model="primary",
            messages=messages,
            max_tokens=self._settings.llm_max_tokens,
            temperature=self._settings.llm_temperature,
        )

        raw = response.choices[0].message.content.strip()
        sql = self._strip_code_fences(raw)

        logger.info(
            "sql_generated",
            question=question,
            sql=sql,
            model=response.model,
        )
        return sql

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        """Remove markdown code fences if present."""
        match = _CODE_FENCE_RE.match(text.strip())
        if match:
            return match.group(1).strip()
        return text.strip()

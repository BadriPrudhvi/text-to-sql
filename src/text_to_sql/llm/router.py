from __future__ import annotations

import structlog
from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel

from text_to_sql.config import Settings

logger = structlog.get_logger()


def create_chat_model(settings: Settings) -> BaseChatModel:
    """Create a LangChain ChatModel with multi-provider fallback chain.

    Fallback order: Anthropic Claude → Google Gemini → OpenAI GPT.
    Only providers with configured API keys are included.
    """
    providers = [
        (settings.anthropic_api_key, settings.default_model, "anthropic"),
        (settings.google_api_key, settings.secondary_model, "google_genai"),
        (settings.openai_api_key, settings.fallback_model, "openai"),
    ]

    models: list[BaseChatModel] = []
    for api_key, model_name, provider in providers:
        if not api_key.get_secret_value():
            continue
        models.append(
            init_chat_model(
                model_name,
                model_provider=provider,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
            )
        )
        logger.info("llm_provider_added", provider=provider, model=model_name)

    if not models:
        raise ValueError(
            "No LLM provider configured. Set at least one of: "
            "ANTHROPIC_API_KEY, GOOGLE_API_KEY, OPENAI_API_KEY"
        )

    primary = models[0]
    if len(models) > 1:
        primary = primary.with_fallbacks(models[1:])
        logger.info("llm_fallback_chain", chain=[type(m).__name__ for m in models])

    return primary

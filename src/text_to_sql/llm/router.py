from __future__ import annotations

import structlog
from langchain_core.language_models.chat_models import BaseChatModel

from text_to_sql.config import Settings

logger = structlog.get_logger()


def create_chat_model(settings: Settings) -> BaseChatModel:
    """Create a LangChain ChatModel with multi-provider fallback chain.

    Fallback order: Anthropic Claude → Google Gemini → OpenAI GPT
    Only providers with configured API keys are included.
    """
    models: list[BaseChatModel] = []

    anthropic_key = settings.anthropic_api_key.get_secret_value()
    if anthropic_key:
        from langchain_anthropic import ChatAnthropic

        models.append(
            ChatAnthropic(
                model=settings.default_model,
                api_key=anthropic_key,
                max_tokens=settings.llm_max_tokens,
                temperature=settings.llm_temperature,
            )
        )
        logger.info("llm_provider_added", provider="anthropic", model=settings.default_model)

    google_key = settings.google_api_key.get_secret_value()
    if google_key:
        from langchain_google_genai import ChatGoogleGenerativeAI

        models.append(
            ChatGoogleGenerativeAI(
                model=settings.secondary_model,
                google_api_key=google_key,
                max_output_tokens=settings.llm_max_tokens,
                temperature=settings.llm_temperature,
            )
        )
        logger.info("llm_provider_added", provider="google", model=settings.secondary_model)

    openai_key = settings.openai_api_key.get_secret_value()
    if openai_key:
        from langchain_openai import ChatOpenAI

        models.append(
            ChatOpenAI(
                model=settings.fallback_model,
                api_key=openai_key,
                max_tokens=settings.llm_max_tokens,
                temperature=settings.llm_temperature,
            )
        )
        logger.info("llm_provider_added", provider="openai", model=settings.fallback_model)

    if not models:
        raise ValueError(
            "No LLM provider configured. Set at least one of: "
            "ANTHROPIC_API_KEY, GOOGLE_API_KEY, OPENAI_API_KEY"
        )

    # Primary model with fallback chain
    primary = models[0]
    if len(models) > 1:
        primary = primary.with_fallbacks(models[1:])
        logger.info(
            "llm_fallback_chain",
            chain=[type(m).__name__ for m in models],
        )

    return primary

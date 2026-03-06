from __future__ import annotations

import structlog
from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import SecretStr

from text_to_sql.config import Settings

logger = structlog.get_logger()


def _detect_provider(model_name: str) -> str | None:
    """Detect the LangChain provider from a model name.

    Returns the provider string or None if unknown.
    """
    name = model_name.lower()
    if name.startswith(("claude-", "claude3")):
        return "anthropic"
    if name.startswith(("gemini-", "gemini/")):
        return "google_genai"
    if name.startswith(("gpt-", "o1-", "o3-", "o4-")):
        return "openai"
    return None


def _api_key_for_provider(
    provider: str, settings: Settings
) -> str | None:
    """Get the API key value for a given provider, or None if not configured."""
    key_map: dict[str, SecretStr] = {
        "anthropic": settings.anthropic_api_key,
        "google_genai": settings.google_api_key,
        "openai": settings.openai_api_key,
    }
    secret = key_map.get(provider)
    if not secret:
        return None
    value = secret.get_secret_value()
    if not value or len(value) < 10:
        return None
    return value


def create_chat_model(settings: Settings) -> BaseChatModel:
    """Create a LangChain ChatModel with multi-provider fallback chain.

    Auto-detects the correct provider for each model name.
    Fallback order: default → secondary → fallback.
    Only models with matching API keys are included.
    """
    model_names = [
        settings.default_model,
        settings.secondary_model,
        settings.fallback_model,
    ]

    models: list[BaseChatModel] = []
    for model_name in model_names:
        if not model_name:
            continue
        provider = _detect_provider(model_name)
        if not provider:
            logger.warning("llm_unknown_provider", model=model_name)
            continue
        api_key = _api_key_for_provider(provider, settings)
        if not api_key:
            logger.debug("llm_no_api_key", provider=provider, model=model_name)
            continue
        try:
            models.append(
                init_chat_model(
                    model_name,
                    model_provider=provider,
                    temperature=settings.llm_temperature,
                    max_tokens=settings.llm_max_tokens,
                    api_key=api_key,
                )
            )
            logger.info("llm_provider_added", provider=provider, model=model_name)
        except Exception:
            logger.warning(
                "llm_provider_skipped",
                provider=provider,
                model=model_name,
                exc_info=True,
            )

    if not models:
        raise ValueError(
            "No LLM provider configured. Set at least one of: "
            "ANTHROPIC_API_KEY, GOOGLE_API_KEY, OPENAI_API_KEY "
            "and ensure model names match (claude-* → Anthropic, "
            "gemini-* → Google, gpt-*/o1-* → OpenAI)"
        )

    primary = models[0]
    if len(models) > 1:
        primary = primary.with_fallbacks(models[1:])
        logger.info("llm_fallback_chain", chain=[type(m).__name__ for m in models])

    return primary


def create_light_chat_model(settings: Settings) -> BaseChatModel | None:
    """Create a lightweight chat model for classification and simple SQL tasks.

    Auto-detects provider from model name.
    Returns None if light_model is not configured or no matching API key.
    """
    if not settings.light_model:
        return None

    provider = _detect_provider(settings.light_model)
    if not provider:
        logger.warning("light_model_unknown_provider", model=settings.light_model)
        return None

    api_key = _api_key_for_provider(provider, settings)
    if not api_key:
        logger.warning(
            "light_model_no_api_key",
            provider=provider,
            model=settings.light_model,
        )
        return None

    try:
        model = init_chat_model(
            settings.light_model,
            model_provider=provider,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            api_key=api_key,
        )
        logger.info(
            "light_model_created",
            provider=provider,
            model=settings.light_model,
        )
        return model
    except Exception:
        logger.warning(
            "light_model_skipped",
            provider=provider,
            model=settings.light_model,
            exc_info=True,
        )
        return None

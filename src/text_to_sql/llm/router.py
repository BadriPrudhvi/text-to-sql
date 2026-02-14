from __future__ import annotations

from litellm import Router

from text_to_sql.config import Settings


def create_llm_router(settings: Settings) -> Router:
    """Configure LiteLLM Router with fallback chains and cost-based routing."""
    model_list = [
        {
            "model_name": "primary",
            "litellm_params": {
                "model": settings.default_model,
                "api_key": settings.anthropic_api_key.get_secret_value(),
            },
        },
        {
            "model_name": "fallback",
            "litellm_params": {
                "model": settings.fallback_model,
                "api_key": settings.openai_api_key.get_secret_value(),
            },
        },
    ]

    return Router(
        model_list=model_list,
        fallbacks=[{"primary": ["fallback"]}],
        routing_strategy=settings.routing_strategy.value,
        num_retries=2,
        timeout=60,
    )

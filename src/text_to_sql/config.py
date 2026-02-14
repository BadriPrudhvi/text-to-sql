from __future__ import annotations

from enum import Enum

from pydantic import ConfigDict, SecretStr, field_validator
from pydantic_settings import BaseSettings


class DatabaseType(str, Enum):
    BIGQUERY = "bigquery"
    POSTGRES = "postgres"
    SQLITE = "sqlite"


class RoutingStrategy(str, Enum):
    COST = "cost-based-routing"
    LATENCY = "latency-based-routing"
    SIMPLE = "simple-shuffle"


class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # LLM Keys
    anthropic_api_key: SecretStr = SecretStr("")
    openai_api_key: SecretStr = SecretStr("")

    # Database
    primary_db_type: DatabaseType = DatabaseType.BIGQUERY
    bigquery_project: str = ""
    bigquery_dataset: str = ""
    bigquery_credentials_path: str = ""
    postgres_url: str = ""
    sqlite_url: str = "sqlite+aiosqlite:///./local.db"

    # LLM Routing
    default_model: str = "anthropic/claude-opus-4-6"
    fallback_model: str = "openai/gpt-5.1-chat-latest"
    routing_strategy: RoutingStrategy = RoutingStrategy.COST
    llm_max_tokens: int = 4096
    llm_temperature: float = 0.0

    # Schema Cache
    schema_cache_ttl_seconds: int = 3600

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    @field_validator("primary_db_type", mode="before")
    @classmethod
    def normalize_db_type(cls, v: str) -> str:
        if isinstance(v, str):
            return v.lower()
        return v


def get_settings() -> Settings:
    return Settings()

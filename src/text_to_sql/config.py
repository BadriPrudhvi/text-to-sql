from __future__ import annotations

from enum import Enum

from pydantic import ConfigDict, SecretStr, field_validator
from pydantic_settings import BaseSettings


class DatabaseType(str, Enum):
    BIGQUERY = "bigquery"
    POSTGRES = "postgres"
    SQLITE = "sqlite"


class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM Keys (provide at least one)
    anthropic_api_key: SecretStr = SecretStr("")
    google_api_key: SecretStr = SecretStr("")
    openai_api_key: SecretStr = SecretStr("")

    # Database
    primary_db_type: DatabaseType = DatabaseType.SQLITE
    bigquery_project: str = ""
    bigquery_dataset: str = ""
    bigquery_credentials_path: str = ""
    postgres_url: str = ""
    sqlite_url: str = "sqlite+aiosqlite:///./chinook.db"

    # LLM Models
    default_model: str = "claude-opus-4-6"
    secondary_model: str = "gemini-3-pro-preview"
    fallback_model: str = "gpt-4o"
    llm_max_tokens: int = 4096
    llm_temperature: float = 0.0

    # Schema Cache
    schema_cache_ttl_seconds: int = 3600

    # SQLite metadata
    sqlite_metadata_path: str = ""

    # Schema filtering
    schema_include_tables: list[str] = []
    schema_exclude_tables: list[str] = []

    # Context window management
    context_max_tokens: int = 16000
    context_schema_budget_pct: float = 0.6
    context_history_max_messages: int = 10

    # Dynamic schema selection
    schema_selection_mode: str = "none"  # "none" | "keyword" | "llm"
    schema_max_selected_tables: int = 15

    # Storage
    storage_type: str = "memory"  # "memory" | "sqlite"
    storage_sqlite_path: str = "./pipeline.db"

    # Cache
    cache_enabled: bool = True
    cache_ttl_seconds: int = 86400

    # Self-correction
    max_correction_attempts: int = 2

    # Analytical query support
    analytical_max_plan_steps: int = 7
    analytical_max_synthesis_attempts: int = 1

    # Reliability
    db_query_timeout_seconds: int = 30
    llm_retry_attempts: int = 3
    llm_retry_min_wait_seconds: int = 2
    llm_retry_max_wait_seconds: int = 10
    rate_limit_requests_per_minute: int = 20

    # LangSmith (optional)
    langsmith_api_key: SecretStr = SecretStr("")
    langsmith_project: str = "text-to-sql"

    # Sessions
    session_timeout_seconds: int = 3600

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

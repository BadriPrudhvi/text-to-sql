from __future__ import annotations

import pytest

from text_to_sql.config import DatabaseType, RoutingStrategy, Settings


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.delenv("PRIMARY_DB_TYPE", raising=False)
    settings = Settings()
    assert settings.primary_db_type == DatabaseType.BIGQUERY
    assert settings.routing_strategy == RoutingStrategy.COST
    assert settings.llm_temperature == 0.0
    assert settings.schema_cache_ttl_seconds == 3600


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("PRIMARY_DB_TYPE", "sqlite")
    monkeypatch.setenv("SQLITE_URL", "sqlite+aiosqlite:///test.db")
    monkeypatch.setenv("DEFAULT_MODEL", "anthropic/claude-sonnet-4-5-20250929")
    settings = Settings()
    assert settings.primary_db_type == DatabaseType.SQLITE
    assert settings.sqlite_url == "sqlite+aiosqlite:///test.db"
    assert settings.default_model == "anthropic/claude-sonnet-4-5-20250929"


def test_db_type_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("PRIMARY_DB_TYPE", "BIGQUERY")
    settings = Settings()
    assert settings.primary_db_type == DatabaseType.BIGQUERY


def test_secret_str_hides_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "super-secret")
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    settings = Settings()
    assert "super-secret" not in str(settings.anthropic_api_key)
    assert settings.anthropic_api_key.get_secret_value() == "super-secret"

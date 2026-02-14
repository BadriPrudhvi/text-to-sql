from __future__ import annotations

import pytest

from text_to_sql.config import DatabaseType, Settings


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.delenv("PRIMARY_DB_TYPE", raising=False)
    settings = Settings()
    assert settings.primary_db_type == DatabaseType.BIGQUERY
    assert settings.llm_temperature == 0.0
    assert settings.schema_cache_ttl_seconds == 3600
    assert settings.default_model == "claude-opus-4-6"
    assert settings.secondary_model == "gemini-2.5-pro"
    assert settings.fallback_model == "gpt-4o"


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("PRIMARY_DB_TYPE", "sqlite")
    monkeypatch.setenv("SQLITE_URL", "sqlite+aiosqlite:///test.db")
    monkeypatch.setenv("DEFAULT_MODEL", "claude-sonnet-4-5-20250929")
    settings = Settings()
    assert settings.primary_db_type == DatabaseType.SQLITE
    assert settings.sqlite_url == "sqlite+aiosqlite:///test.db"
    assert settings.default_model == "claude-sonnet-4-5-20250929"


def test_google_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("GOOGLE_API_KEY", "google-secret")
    settings = Settings()
    assert settings.google_api_key.get_secret_value() == "google-secret"


def test_db_type_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("PRIMARY_DB_TYPE", "BIGQUERY")
    settings = Settings()
    assert settings.primary_db_type == DatabaseType.BIGQUERY


def test_secret_str_hides_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "super-secret")
    settings = Settings()
    assert "super-secret" not in str(settings.anthropic_api_key)
    assert settings.anthropic_api_key.get_secret_value() == "super-secret"


def test_all_api_keys_default_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    settings = Settings()
    assert settings.anthropic_api_key.get_secret_value() == ""
    assert settings.google_api_key.get_secret_value() == ""
    assert settings.openai_api_key.get_secret_value() == ""

from __future__ import annotations

from pathlib import Path

import pytest

from blacklight.providers.base import LLMProvider
from blacklight.providers.mock import MockProvider
from blacklight.sdk import client as sdk_client
from blacklight.sdk import Blacklight
from blacklight.settings import Settings


def test_sdk_exports_blacklight():
    assert Blacklight.__name__ == "Blacklight"


def test_blacklight_mock_constructs_without_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_PROVIDER", "injected")
    monkeypatch.setenv("LLM_PROVIDER_ADAPTER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)

    client = Blacklight.mock(trace_db_path=tmp_path / "traces.sqlite3")

    assert client.provider_source == "mock"
    assert client.provider_name == "mock"
    assert client.model == "mock-ticket-classifier"
    assert client.trace_db_path == str(tmp_path / "traces.sqlite3")


def test_blacklight_from_settings_uses_configured_runtime(tmp_path):
    client = Blacklight.from_settings(
        Settings(
            provider="mock",
            model="mock-sdk-model",
            trace_db_path=str(tmp_path / "settings.sqlite3"),
        )
    )

    assert client.provider_source == "mock"
    assert client.provider_name == "mock"
    assert client.model == "mock-sdk-model"
    assert client.trace_db_path == str(tmp_path / "settings.sqlite3")


def test_blacklight_from_settings_can_load_user_env(tmp_path):
    user_env_path = tmp_path / "user.env"
    user_env_path.write_text(
        "\n".join(
            [
                "LLM_PROVIDER=mock",
                "LLM_MODEL=mock-from-user-env",
                f"TRACE_DB_PATH={tmp_path / 'user-env.sqlite3'}",
            ]
        ),
        encoding="utf-8",
    )

    client = Blacklight.from_settings(user_env_path=user_env_path)

    assert client.provider_name == "mock"
    assert client.provider_source == "mock"
    assert client.model == "mock-from-user-env"
    assert client.trace_db_path == str(tmp_path / "user-env.sqlite3")


def test_blacklight_from_provider_uses_explicit_provider(tmp_path):
    provider = MockProvider()

    client = Blacklight.from_provider(
        provider,
        model="explicit-model",
        trace_db_path=tmp_path / "provider.sqlite3",
    )

    assert client.provider_source == "injected"
    assert client.provider_name == "mock"
    assert client.model == "explicit-model"
    assert client.trace_db_path == str(tmp_path / "provider.sqlite3")


def test_blacklight_from_provider_rejects_non_provider():
    with pytest.raises(TypeError, match="LLMProvider"):
        Blacklight.from_provider(object(), model="bad")  # type: ignore[arg-type]


def test_blacklight_from_provider_accepts_provider_subclasses(tmp_path):
    class CustomProvider(MockProvider):
        name = "custom-sdk-provider"

    provider: LLMProvider = CustomProvider()

    client = Blacklight.from_provider(
        provider,
        model="custom-model",
        trace_db_path=Path(tmp_path / "custom.sqlite3"),
    )

    assert client.provider_name == "custom-sdk-provider"
    assert client.provider_source == "injected"
    assert client.model == "custom-model"


def test_blacklight_from_settings_marks_non_mock_as_injected(monkeypatch):
    class CustomProvider(MockProvider):
        name = "settings-custom-provider"

    provider = CustomProvider()
    monkeypatch.setattr(sdk_client, "create_provider", lambda _settings: provider)

    client = Blacklight.from_settings(
        Settings(
            provider="injected",
            provider_adapter="custom",
            custom_provider_path="my_app.providers:Provider",
            model="settings-custom-model",
        )
    )

    assert client.provider_source == "injected"
    assert client.provider_name == "settings-custom-provider"

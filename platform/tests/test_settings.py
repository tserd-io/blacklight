import pytest

from blacklight.settings import load_settings, load_user_env, write_user_env


def test_provider_reliability_settings_load_from_environment(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("LLM_PROVIDER_MAX_RETRIES", "4")
    monkeypatch.setenv("LLM_PROVIDER_RATE_LIMIT_REQUESTS", "8")
    monkeypatch.setenv("LLM_PROVIDER_RATE_LIMIT_WINDOW_SECONDS", "20.5")

    settings = load_settings()

    assert settings.provider_timeout_seconds == 12.5
    assert settings.provider_max_retries == 4
    assert settings.provider_rate_limit_requests == 8
    assert settings.provider_rate_limit_window_seconds == 20.5


def test_settings_load_from_user_env_when_process_env_is_absent(monkeypatch, tmp_path):
    user_env_path = tmp_path / "user.env"
    user_env_path.write_text(
        "\n".join(
            [
                "LLM_PROVIDER=custom",
                "LLM_MODEL=local-model",
                "TRACE_DB_PATH=local.sqlite3",
                "LLM_CUSTOM_PROVIDER=my_package.providers:Provider",
                "OLLAMA_BASE_URL=http://localhost:11435",
                "LLM_PROVIDER_TIMEOUT_SECONDS=9.5",
                "LLM_PROVIDER_MAX_RETRIES=5",
                "LLM_PROVIDER_RATE_LIMIT_REQUESTS=11",
                "LLM_PROVIDER_RATE_LIMIT_WINDOW_SECONDS=30",
            ]
        ),
        encoding="utf-8",
    )
    for key in [
        "LLM_PROVIDER",
        "LLM_MODEL",
        "TRACE_DB_PATH",
        "LLM_CUSTOM_PROVIDER",
        "OLLAMA_BASE_URL",
        "LLM_PROVIDER_TIMEOUT_SECONDS",
        "LLM_PROVIDER_MAX_RETRIES",
        "LLM_PROVIDER_RATE_LIMIT_REQUESTS",
        "LLM_PROVIDER_RATE_LIMIT_WINDOW_SECONDS",
    ]:
        monkeypatch.delenv(key, raising=False)

    settings = load_settings(user_env_path)

    assert settings.provider == "custom"
    assert settings.model == "local-model"
    assert settings.trace_db_path == "local.sqlite3"
    assert settings.custom_provider_path == "my_package.providers:Provider"
    assert settings.ollama_base_url == "http://localhost:11435"
    assert settings.provider_timeout_seconds == 9.5
    assert settings.provider_max_retries == 5
    assert settings.provider_rate_limit_requests == 11
    assert settings.provider_rate_limit_window_seconds == 30


def test_process_env_takes_precedence_over_user_env(monkeypatch, tmp_path):
    user_env_path = tmp_path / "user.env"
    user_env_path.write_text("LLM_PROVIDER=custom\nLLM_MODEL=user-env-model\n", encoding="utf-8")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("LLM_MODEL", "process-env-model")

    settings = load_settings(user_env_path)

    assert settings.provider == "mock"
    assert settings.model == "process-env-model"


def test_private_provider_key_is_loaded_only_from_process_env(monkeypatch, tmp_path):
    user_env_path = tmp_path / "user.env"
    user_env_path.write_text("OPENAI_API_KEY=sk-user-env-secret\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert load_settings(user_env_path).openai_api_key is None

    monkeypatch.setenv("OPENAI_API_KEY", "sk-private-process-secret")

    assert load_settings(user_env_path).openai_api_key == "sk-private-process-secret"


def test_write_user_env_preserves_private_unknown_lines_and_rejects_unknown_settings(tmp_path):
    user_env_path = tmp_path / "user.env"
    user_env_path.write_text(
        "# app-managed settings\nPRIVATE_OPERATOR_VALUE=leave-me-alone\nLLM_PROVIDER=mock\n",
        encoding="utf-8",
    )

    values = write_user_env(
        {
            "LLM_PROVIDER": "openai",
            "OLLAMA_BASE_URL": "http://localhost:11434",
        },
        user_env_path,
    )
    written = user_env_path.read_text(encoding="utf-8")

    assert values["LLM_PROVIDER"] == "openai"
    assert values["OLLAMA_BASE_URL"] == "http://localhost:11434"
    assert "PRIVATE_OPERATOR_VALUE=leave-me-alone" in written
    assert "OLLAMA_BASE_URL=http://localhost:11434" in written

    with pytest.raises(ValueError, match="Unsupported user.env setting"):
        write_user_env({"SHELL": "powershell"}, user_env_path)

    with pytest.raises(ValueError, match="Unsupported user.env setting"):
        write_user_env({"OPENAI_API_KEY": "sk-secret"}, user_env_path)


def test_write_user_env_removes_keys_with_none_value(tmp_path):
    user_env_path = tmp_path / "user.env"
    user_env_path.write_text(
        "LLM_PROVIDER=mock\nOLLAMA_BASE_URL=http://localhost:11434\n",
        encoding="utf-8",
    )

    write_user_env({"OLLAMA_BASE_URL": None}, user_env_path)

    values = load_user_env(user_env_path)
    assert "OLLAMA_BASE_URL" not in values
    assert "LLM_PROVIDER" in values

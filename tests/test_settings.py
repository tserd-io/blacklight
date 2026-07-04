from llm_platform_starter.settings import load_settings


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

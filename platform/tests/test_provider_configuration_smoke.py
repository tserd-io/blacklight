import json
import os

import pytest

from llm_platform_starter.models import ProviderRequest, ProviderResponse
from llm_platform_starter.providers.factory import create_provider
from llm_platform_starter.providers.mock import MockProvider
from llm_platform_starter.settings import Settings, load_settings


SMOKE_PROMPT = "Classify this synthetic support ticket: duplicate billing after renewal."


def _request(model: str) -> ProviderRequest:
    return ProviderRequest(
        prompt=SMOKE_PROMPT,
        model=model,
        metadata={"idempotency_key": "provider-configuration-smoke"},
    )


def _skip_unless_enabled(flag_name: str, reason: str) -> None:
    if os.getenv(flag_name) != "1":
        pytest.skip(f"Set {flag_name}=1 to run this opt-in smoke test. {reason}")


def test_mock_provider_configuration_smoke_runs_in_default_ci(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    settings = load_settings()
    provider = create_provider(settings)
    response = provider.complete(_request(settings.model))
    payload = json.loads(response.text)

    assert isinstance(provider, MockProvider)
    assert response.provider == "mock"
    assert response.model == "mock-ticket-classifier"
    assert payload["category"] == "billing"


def test_openai_provider_configuration_smoke_is_opt_in():
    _skip_unless_enabled(
        "RUN_OPENAI_PROVIDER_SMOKE",
        "Requires OPENAI_API_KEY and an OpenAI model in LLM_MODEL.",
    )
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY is required for the OpenAI provider smoke test.")

    settings = Settings(
        provider="openai",
        model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        openai_api_key=os.environ["OPENAI_API_KEY"],
    )
    response = create_provider(settings).complete(_request(settings.model))

    assert response.provider == "openai"
    assert response.model == settings.model
    assert response.text.strip()


def test_custom_provider_configuration_smoke_is_opt_in():
    _skip_unless_enabled(
        "RUN_CUSTOM_PROVIDER_SMOKE",
        "Requires LLM_CUSTOM_PROVIDER to point at a real provider import path.",
    )
    custom_provider_path = os.getenv("LLM_CUSTOM_PROVIDER")
    if not custom_provider_path:
        pytest.skip("LLM_CUSTOM_PROVIDER is required for the custom provider smoke test.")

    settings = Settings(
        provider="custom",
        model=os.getenv("LLM_MODEL", "custom-smoke-model"),
        custom_provider_path=custom_provider_path,
    )
    response = create_provider(settings).complete(_request(settings.model))

    assert isinstance(response, ProviderResponse)
    assert response.provider
    assert response.model == settings.model
    assert response.text is not None


def test_local_endpoint_provider_configuration_smoke_is_opt_in():
    _skip_unless_enabled(
        "RUN_LOCAL_PROVIDER_SMOKE",
        "Requires LLM_CUSTOM_PROVIDER to point at a local endpoint adapter.",
    )
    custom_provider_path = os.getenv("LLM_CUSTOM_PROVIDER")
    if not custom_provider_path:
        pytest.skip("LLM_CUSTOM_PROVIDER is required for the local endpoint smoke test.")

    settings = Settings(
        provider="custom",
        model=os.getenv("LLM_MODEL", "local-smoke-model"),
        custom_provider_path=custom_provider_path,
    )
    response = create_provider(settings).complete(_request(settings.model))

    assert isinstance(response, ProviderResponse)
    assert response.provider
    assert response.model == settings.model
    assert response.text is not None

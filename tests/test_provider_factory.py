import pytest

from llm_platform_starter.examples.ticket_classifier import TicketClassifier
from llm_platform_starter.models import ProviderRequest, ProviderResponse, TicketRequest
from llm_platform_starter.providers.base import LLMProvider
from llm_platform_starter.providers.factory import ProviderConfigurationError, create_provider
from llm_platform_starter.providers.mock import MockProvider
from llm_platform_starter.settings import Settings, load_settings


def test_provider_factory_creates_mock_provider_by_default():
    provider = create_provider(Settings())

    assert isinstance(provider, MockProvider)


def test_provider_factory_rejects_unknown_provider():
    with pytest.raises(ProviderConfigurationError, match="Unsupported LLM_PROVIDER"):
        create_provider(Settings(provider="anthropic"))


def test_provider_factory_requires_openai_api_key():
    with pytest.raises(ProviderConfigurationError, match="OPENAI_API_KEY"):
        create_provider(Settings(provider="openai", openai_api_key=None))


def test_provider_factory_creates_custom_provider_from_import_path(tmp_path, monkeypatch):
    provider_module = tmp_path / "custom_provider.py"
    provider_module.write_text(
        """
from llm_platform_starter.models import ProviderResponse
from llm_platform_starter.providers.base import LLMProvider


class CustomProvider(LLMProvider):
    name = "custom-test"

    def complete(self, request):
        return ProviderResponse(text="{}", provider=self.name, model=request.model)
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    provider = create_provider(
        Settings(provider="custom", custom_provider_path="custom_provider:CustomProvider")
    )

    assert isinstance(provider, LLMProvider)
    assert provider.name == "custom-test"


def test_provider_factory_creates_custom_provider_from_factory(tmp_path, monkeypatch):
    provider_module = tmp_path / "custom_factory.py"
    provider_module.write_text(
        """
from llm_platform_starter.models import ProviderResponse
from llm_platform_starter.providers.base import LLMProvider


class CustomProvider(LLMProvider):
    name = "custom-factory"

    def complete(self, request):
        return ProviderResponse(text="{}", provider=self.name, model=request.model)


def build_provider():
    return CustomProvider()
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    provider = create_provider(
        Settings(provider="custom", custom_provider_path="custom_factory:build_provider")
    )

    response = provider.complete(ProviderRequest(prompt="hello", model="custom-model"))

    assert response == ProviderResponse(text="{}", provider="custom-factory", model="custom-model")


def test_provider_factory_creates_custom_provider_from_instance(tmp_path, monkeypatch):
    provider_module = tmp_path / "custom_instance.py"
    provider_module.write_text(
        """
from llm_platform_starter.models import ProviderResponse
from llm_platform_starter.providers.base import LLMProvider


class CustomProvider(LLMProvider):
    name = "custom-instance"

    def complete(self, request):
        return ProviderResponse(text="{}", provider=self.name, model=request.model)


provider = CustomProvider()
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    provider = create_provider(
        Settings(provider="custom", custom_provider_path="custom_instance:provider")
    )

    assert isinstance(provider, LLMProvider)
    assert provider.name == "custom-instance"


def test_provider_factory_requires_custom_provider_path():
    with pytest.raises(ProviderConfigurationError, match="LLM_CUSTOM_PROVIDER"):
        create_provider(Settings(provider="custom"))


def test_provider_factory_rejects_malformed_custom_provider_path():
    with pytest.raises(ProviderConfigurationError, match="module:attribute"):
        create_provider(Settings(provider="custom", custom_provider_path="bad.path"))


def test_provider_factory_rejects_missing_custom_provider_module():
    with pytest.raises(ProviderConfigurationError, match="Could not import"):
        create_provider(Settings(provider="custom", custom_provider_path="missing_module:Provider"))


def test_provider_factory_rejects_missing_custom_provider_attribute(tmp_path, monkeypatch):
    provider_module = tmp_path / "empty_provider.py"
    provider_module.write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))

    with pytest.raises(ProviderConfigurationError, match="was not found"):
        create_provider(Settings(provider="custom", custom_provider_path="empty_provider:Provider"))


def test_provider_factory_rejects_custom_provider_with_wrong_type(tmp_path, monkeypatch):
    provider_module = tmp_path / "bad_provider.py"
    provider_module.write_text("bad_provider = object()\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))

    with pytest.raises(ProviderConfigurationError, match="LLMProvider"):
        create_provider(Settings(provider="custom", custom_provider_path="bad_provider:bad_provider"))


def test_provider_factory_loads_custom_provider_from_environment(tmp_path, monkeypatch):
    provider_module = tmp_path / "env_provider.py"
    provider_module.write_text(
        """
from llm_platform_starter.models import ProviderResponse
from llm_platform_starter.providers.base import LLMProvider


class EnvProvider(LLMProvider):
    name = "env-custom"

    def complete(self, request):
        return ProviderResponse(text="{}", provider=self.name, model=request.model)
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv("LLM_PROVIDER", "custom")
    monkeypatch.setenv("LLM_CUSTOM_PROVIDER", "env_provider:EnvProvider")

    provider = create_provider(load_settings())

    assert provider.name == "env-custom"


def test_ticket_classifier_uses_custom_provider_loaded_from_factory(tmp_path, monkeypatch):
    provider_module = tmp_path / "classifier_provider.py"
    provider_module.write_text(
        """
import json

from llm_platform_starter.models import ProviderResponse
from llm_platform_starter.providers.base import LLMProvider


class ClassifierProvider(LLMProvider):
    name = "classifier-custom"

    def complete(self, request):
        payload = {
            "category": "technical",
            "severity": "low",
            "confidence": 0.81,
            "rationale": "Custom provider fixture response.",
            "needs_review": False,
        }
        return ProviderResponse(
            text=json.dumps(payload),
            provider=self.name,
            model=request.model,
        )
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    settings = Settings(
        provider="custom",
        model="custom-ticket-classifier",
        custom_provider_path="classifier_provider:ClassifierProvider",
    )
    classifier = TicketClassifier(provider=create_provider(settings), model=settings.model)

    result = classifier.classify(TicketRequest(subject="API error", body="Export failed."))

    assert result.category.value == "technical"
    assert result.rationale == "Custom provider fixture response."

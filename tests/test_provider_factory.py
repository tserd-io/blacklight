import pytest

from llm_platform_starter.providers.factory import ProviderConfigurationError, create_provider
from llm_platform_starter.providers.mock import MockProvider
from llm_platform_starter.settings import Settings


def test_provider_factory_creates_mock_provider_by_default():
    provider = create_provider(Settings())

    assert isinstance(provider, MockProvider)


def test_provider_factory_rejects_unknown_provider():
    with pytest.raises(ProviderConfigurationError, match="Unsupported LLM_PROVIDER"):
        create_provider(Settings(provider="anthropic"))


def test_provider_factory_requires_openai_api_key():
    with pytest.raises(ProviderConfigurationError, match="OPENAI_API_KEY"):
        create_provider(Settings(provider="openai", openai_api_key=None))

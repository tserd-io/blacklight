from __future__ import annotations

from llm_platform_starter.providers.base import LLMProvider
from llm_platform_starter.providers.mock import MockProvider
from llm_platform_starter.settings import Settings, load_settings


class ProviderConfigurationError(ValueError):
    """Raised when provider settings cannot produce a configured provider."""


def create_provider(settings: Settings | None = None) -> LLMProvider:
    resolved_settings = settings or load_settings()
    provider_name = resolved_settings.provider.strip().lower()

    if provider_name == "mock":
        return MockProvider()

    if provider_name == "openai":
        if not resolved_settings.openai_api_key:
            raise ProviderConfigurationError(
                "OPENAI_API_KEY is required when LLM_PROVIDER is set to openai."
            )
        from llm_platform_starter.providers.openai_provider import OpenAIProvider

        return OpenAIProvider(api_key=resolved_settings.openai_api_key)

    raise ProviderConfigurationError(
        f"Unsupported LLM_PROVIDER={resolved_settings.provider!r}. "
        "Supported providers are: mock, openai."
    )

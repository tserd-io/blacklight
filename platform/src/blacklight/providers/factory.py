from __future__ import annotations

from importlib import import_module
from inspect import isclass
from typing import Any

from blacklight.providers.base import LLMProvider
from blacklight.providers.mock import MockProvider
from blacklight.settings import Settings, load_settings


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
        from blacklight.providers.openai_provider import OpenAIProvider

        return OpenAIProvider(api_key=resolved_settings.openai_api_key)

    if provider_name == "custom":
        if not resolved_settings.custom_provider_path:
            raise ProviderConfigurationError(
                "LLM_CUSTOM_PROVIDER is required when LLM_PROVIDER is set to custom. "
                "Use an import path like 'my_package.providers:MyProvider'."
            )
        return _load_custom_provider(resolved_settings.custom_provider_path)

    raise ProviderConfigurationError(
        f"Unsupported LLM_PROVIDER={resolved_settings.provider!r}. "
        "Supported providers are: mock, openai, custom."
    )


def _load_custom_provider(import_path: str) -> LLMProvider:
    module_name, separator, attribute_name = import_path.partition(":")
    if not separator or not module_name or not attribute_name:
        raise ProviderConfigurationError(
            "LLM_CUSTOM_PROVIDER must use 'module:attribute' format, "
            f"got {import_path!r}."
        )

    try:
        module = import_module(module_name)
    except ImportError as exc:
        raise ProviderConfigurationError(
            f"Could not import custom provider module {module_name!r}."
        ) from exc

    try:
        target: Any = getattr(module, attribute_name)
    except AttributeError as exc:
        raise ProviderConfigurationError(
            f"Custom provider attribute {attribute_name!r} was not found in {module_name!r}."
        ) from exc

    provider = target() if isclass(target) else target
    if callable(provider) and not isinstance(provider, LLMProvider):
        provider = provider()

    if not isinstance(provider, LLMProvider):
        raise ProviderConfigurationError(
            "LLM_CUSTOM_PROVIDER must resolve to an LLMProvider instance, "
            "an LLMProvider subclass, or a zero-argument factory returning one."
        )
    return provider

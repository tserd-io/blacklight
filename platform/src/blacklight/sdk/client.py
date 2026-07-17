from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from blacklight.providers.base import LLMProvider
from blacklight.providers.factory import create_provider
from blacklight.providers.mock import MockProvider
from blacklight.sdk.evals import EvalClient
from blacklight.sdk.providers import ProviderClient
from blacklight.sdk.traces import TraceClient
from blacklight.sdk.workflows import WorkflowClient
from blacklight.settings import Settings, load_settings

ProviderSource = Literal["mock", "injected"]


@dataclass(frozen=True)
class Blacklight:
    """Stable entry point for embedding Blacklight without importing internal modules."""

    _provider: LLMProvider
    _settings: Settings
    _provider_source: ProviderSource

    @classmethod
    def mock(
        cls,
        *,
        trace_db_path: str | Path = "traces.sqlite3",
        model: str = "mock-ticket-classifier",
    ) -> Blacklight:
        """Create a deterministic mock-mode client without reading environment settings."""
        settings = Settings(
            provider="mock",
            model=model,
            trace_db_path=str(trace_db_path),
        )
        return cls(
            _provider=MockProvider(),
            _settings=settings,
            _provider_source="mock",
        )

    @classmethod
    def from_settings(
        cls,
        settings: Settings | None = None,
        *,
        user_env_path: str | Path | None = None,
    ) -> Blacklight:
        """Create a client from explicit settings or the normal runtime configuration."""
        resolved_settings = settings or load_settings(user_env_path)
        return cls(
            _provider=create_provider(resolved_settings),
            _settings=resolved_settings,
            _provider_source="mock" if resolved_settings.provider == "mock" else "injected",
        )

    @classmethod
    def from_provider(
        cls,
        provider: LLMProvider,
        *,
        model: str,
        trace_db_path: str | Path = "traces.sqlite3",
    ) -> Blacklight:
        """Create a client from an already constructed provider."""
        if not isinstance(provider, LLMProvider):
            raise TypeError("provider must implement LLMProvider.")
        settings = Settings(
            provider="injected",
            provider_name=provider.name,
            model=model,
            trace_db_path=str(trace_db_path),
        )
        return cls(
            _provider=provider,
            _settings=settings,
            _provider_source="injected",
        )

    @property
    def provider_source(self) -> ProviderSource:
        return self._provider_source

    @property
    def provider_name(self) -> str:
        return self._provider.name

    @property
    def model(self) -> str:
        return self._settings.model

    @property
    def trace_db_path(self) -> str:
        return self._settings.trace_db_path

    @property
    def workflows(self) -> WorkflowClient:
        return WorkflowClient(provider=self._provider, settings=self._settings)

    @property
    def traces(self) -> TraceClient:
        return TraceClient(settings=self._settings)

    @property
    def evals(self) -> EvalClient:
        return EvalClient(
            provider=self._provider,
            settings=self._settings,
            provider_source=self._provider_source,
        )

    @property
    def providers(self) -> ProviderClient:
        return ProviderClient(settings=self._settings)

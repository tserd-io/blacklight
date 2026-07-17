from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from blacklight.provider_readiness import (
    provider_health_payload,
    provider_list_payload,
    provider_status_payload,
)
from blacklight.settings import Settings


class ProviderHealth(BaseModel):
    provider: str
    provider_adapter: str | None = None
    provider_name: str | None = None
    model: str
    trace_db_path: str
    provider_key_configured: bool
    custom_adapter_configured: bool
    ollama_base_url: str
    provider_timeout_seconds: float
    provider_max_retries: int
    provider_rate_limit_requests: int
    provider_rate_limit_window_seconds: float


class ProviderListResult(BaseModel):
    active_provider: str
    providers: list[dict[str, Any]] = Field(default_factory=list)


class ProviderStatus(BaseModel):
    runtime: ProviderHealth
    providers: dict[str, dict[str, Any]]
    local_model: dict[str, Any]


class ProviderClient:
    def __init__(self, *, settings: Settings) -> None:
        self._settings = settings

    def health(self) -> ProviderHealth:
        return ProviderHealth.model_validate(provider_health_payload(self._settings))

    def list(self) -> ProviderListResult:
        return ProviderListResult.model_validate(provider_list_payload(self._settings))

    def status(self, *, include_local_probe: bool = True) -> ProviderStatus:
        return ProviderStatus.model_validate(
            provider_status_payload(
                self._settings,
                include_local_probe=include_local_probe,
            )
        )

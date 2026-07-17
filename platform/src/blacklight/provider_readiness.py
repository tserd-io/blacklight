from __future__ import annotations

from typing import Any

from blacklight.local_models import (
    DEFAULT_LOCAL_MODEL,
    DEFAULT_OLLAMA_BASE_URL,
    OLLAMA_PROVIDER_PATH,
    local_model_status,
)
from blacklight.settings import Settings


def provider_health_payload(settings: Settings) -> dict[str, Any]:
    return {
        "provider": settings.provider,
        "provider_adapter": settings.provider_adapter,
        "provider_name": settings.provider_name,
        "model": settings.model,
        "trace_db_path": settings.trace_db_path,
        "provider_key_configured": bool(settings.openai_api_key),
        "custom_adapter_configured": bool(settings.custom_provider_path),
        "ollama_base_url": settings.ollama_base_url,
        "provider_timeout_seconds": settings.provider_timeout_seconds,
        "provider_max_retries": settings.provider_max_retries,
        "provider_rate_limit_requests": settings.provider_rate_limit_requests,
        "provider_rate_limit_window_seconds": settings.provider_rate_limit_window_seconds,
    }


def provider_list_payload(settings: Settings) -> dict[str, Any]:
    return {
        "active_provider": settings.provider,
        "providers": [
            {
                "name": "mock",
                "configured": True,
                "selected": settings.provider == "mock",
                "requires_secret": False,
                "summary": "Deterministic demo mode for learning features, tests, and CI.",
            },
            {
                "name": "hosted",
                "configured": bool(settings.openai_api_key),
                "selected": (
                    settings.provider == "injected"
                    and settings.provider_adapter == "openai"
                ),
                "requires_secret": True,
                "summary": "Injected hosted adapter example using a private provider key.",
            },
            {
                "name": "custom",
                "configured": bool(settings.custom_provider_path),
                "selected": (
                    settings.provider == "injected"
                    and settings.provider_adapter == "custom"
                ),
                "requires_secret": False,
                "summary": "Injected adapter path for local, hosted, or private user-owned providers.",
            },
        ],
    }


def provider_status_payload(
    settings: Settings,
    *,
    include_local_probe: bool = True,
    compact_local_model: bool = False,
) -> dict[str, Any]:
    local_status = (
        local_model_status(settings).as_dict()
        if include_local_probe
        else local_model_config_status(settings)
    )
    if compact_local_model:
        local_status = _compact_local_model_status(local_status)
    return {
        "runtime": provider_health_payload(settings),
        "providers": provider_readiness_payload(settings),
        "local_model": local_status,
    }


def provider_readiness_payload(settings: Settings) -> dict[str, dict[str, Any]]:
    return {
        "mock": {
            "configured": True,
            "ready": True,
            "selected": settings.provider == "mock",
            "message": "Mock demonstration mode is ready without live credentials.",
        },
        "hosted": {
            "configured": bool(settings.openai_api_key),
            "ready": bool(settings.openai_api_key),
            "selected": (
                settings.provider == "injected"
                and settings.provider_adapter == "openai"
            ),
            "message": (
                "Injected hosted adapter key is available."
                if settings.openai_api_key
                else "The hosted adapter requires OPENAI_API_KEY, LLM_API_KEY, or API_KEY in a private environment."
            ),
        },
        "custom": {
            "configured": bool(settings.custom_provider_path),
            "ready": bool(settings.custom_provider_path),
            "selected": (
                settings.provider == "injected"
                and settings.provider_adapter == "custom"
            ),
            "message": (
                "Injected provider import path is available."
                if settings.custom_provider_path
                else "Injected provider adapters require LLM_CUSTOM_PROVIDER."
            ),
        },
    }


def local_model_config_status(settings: Settings) -> dict[str, Any]:
    selected = (
        settings.provider == "injected"
        and settings.provider_adapter == "custom"
        and bool(settings.custom_provider_path)
        and "ollama_provider" in settings.custom_provider_path
    )
    model = settings.model if selected else DEFAULT_LOCAL_MODEL
    return {
        "runtime": "ollama",
        "model": model,
        "base_url": settings.ollama_base_url or DEFAULT_OLLAMA_BASE_URL,
        "provider_path": settings.custom_provider_path or OLLAMA_PROVIDER_PATH,
        "configured": selected or settings.ollama_base_url != DEFAULT_OLLAMA_BASE_URL,
        "selected": selected,
        "installed": None,
        "available_models": [],
        "loading": False,
        "ready": None,
        "unavailable": None,
        "status": "not_probed",
        "status_message": (
            "Local model endpoint was not probed. "
            "Call providers.status(include_local_probe=True) for runtime readiness."
        ),
        "start_command": "docker compose -f docker-compose.ollama.yml up -d",
        "install_command": (
            f"docker compose -f docker-compose.ollama.yml exec ollama ollama pull {model}"
        ),
        "fallback": {
            "type": "local_model",
            "configured": None,
            "provider": "ollama",
            "model": model,
            "message": "Local fallback readiness was not checked.",
        },
        "tradeoffs": {},
    }


def _compact_local_model_status(local_status: dict[str, Any]) -> dict[str, Any]:
    return {
        "runtime": local_status["runtime"],
        "configured": local_status["configured"],
        "selected": local_status["selected"],
        "status": local_status["status"],
        "ready": local_status["ready"],
        "message": local_status["status_message"],
    }

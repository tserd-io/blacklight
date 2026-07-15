from __future__ import annotations

import json
import os
import socket
from dataclasses import dataclass
from ipaddress import ip_address
from urllib import error as urlerror
from urllib import request as urlrequest
from urllib.parse import urlparse

from blacklight.settings import Settings


OLLAMA_PROVIDER_PATH = "blacklight.providers.ollama_provider:OllamaProvider"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_LOCAL_MODEL = "llama3.1"


@dataclass(frozen=True)
class LocalModelStatus:
    runtime: str
    model: str
    base_url: str
    provider_path: str
    configured: bool
    selected: bool
    installed: bool
    available_models: list[str]
    loading: bool
    ready: bool
    unavailable: bool
    status: str
    status_message: str
    start_command: str
    install_command: str
    fallback: dict[str, object]
    tradeoffs: dict[str, str]

    def as_dict(self) -> dict[str, object]:
        return {
            "runtime": self.runtime,
            "model": self.model,
            "base_url": self.base_url,
            "provider_path": self.provider_path,
            "configured": self.configured,
            "selected": self.selected,
            "installed": self.installed,
            "available_models": self.available_models,
            "loading": self.loading,
            "ready": self.ready,
            "unavailable": self.unavailable,
            "status": self.status,
            "status_message": self.status_message,
            "start_command": self.start_command,
            "install_command": self.install_command,
            "fallback": self.fallback,
            "tradeoffs": self.tradeoffs,
        }


def local_model_status(settings: Settings, timeout_seconds: float = 0.5) -> LocalModelStatus:
    runtime = "ollama"
    base_url = (os.getenv("OLLAMA_BASE_URL") or settings.ollama_base_url).rstrip("/")
    provider_path = settings.custom_provider_path or OLLAMA_PROVIDER_PATH
    selected = (
        settings.provider == "injected"
        and settings.provider_adapter == "custom"
        and bool(settings.custom_provider_path)
        and "ollama_provider" in settings.custom_provider_path
    )
    model = settings.model if selected else DEFAULT_LOCAL_MODEL
    configured = selected or base_url != DEFAULT_OLLAMA_BASE_URL
    fallback = {
        "type": "local_model",
        "configured": False,
        "provider": "ollama",
        "model": model,
        "message": "Local model fallback is unavailable until the runtime is reachable and the model is installed.",
    }
    hosted_provider = {
        "configured": bool(settings.openai_api_key),
        "provider": "hosted" if settings.openai_api_key else None,
        "secret_source": "private_environment",
        "message": (
            "Configured hosted adapter credentials are available privately."
            if settings.openai_api_key
            else "Hosted adapter credentials are not configured. Keep API keys in private environment settings, not app-editable user.env."
        ),
    }
    tradeoffs = {
        "privacy_control": "Local inference can keep prompts on the user's machine or network.",
        "package_size": "Bundling a model increases installer size; first-run downloads keep the app smaller.",
        "hardware": "Local models depend on available RAM, CPU/GPU, and model size.",
        "quality": "Smaller local models may need review or a private hosted provider for difficult or high-stakes tasks.",
        "support": "A managed app should show model status, disk use, updates, and recovery steps.",
    }
    start_command = "docker compose -f docker-compose.ollama.yml up -d"
    install_command = f"docker compose -f docker-compose.ollama.yml exec ollama ollama pull {model}"

    url_error = _validate_local_base_url(base_url)
    if url_error:
        return LocalModelStatus(
            runtime=runtime,
            model=model,
            base_url=base_url,
            provider_path=provider_path,
            configured=False,
            selected=selected,
            installed=False,
            available_models=[],
            loading=False,
            ready=False,
            unavailable=True,
            status="unavailable",
            status_message=url_error,
            start_command=start_command,
            install_command=install_command,
            fallback={**fallback, "hosted_provider": hosted_provider},
            tradeoffs=tradeoffs,
        )

    probe = _probe_ollama(base_url=base_url, model=model, timeout_seconds=timeout_seconds)
    ready = probe["status"] == "ready"
    status_message = str(probe["message"])
    if ready and not selected:
        status_message = (
            f"Local fallback model {model} is installed and ready. "
            "Set LLM_PROVIDER=injected, LLM_PROVIDER_ADAPTER=custom, "
            f"and LLM_CUSTOM_PROVIDER={OLLAMA_PROVIDER_PATH} to make it active."
        )
    return LocalModelStatus(
        runtime=runtime,
        model=model,
        base_url=base_url,
        provider_path=provider_path,
        configured=configured,
        selected=selected,
        installed=probe["installed"],
        available_models=probe["available_models"],
        loading=probe["status"] == "loading",
        ready=ready,
        unavailable=probe["status"] == "unavailable",
        status=probe["status"],
        status_message=status_message,
        start_command=start_command,
        install_command=install_command,
        fallback={
            **fallback,
            "configured": ready,
            "message": (
                f"Local fallback is available through {model}."
                if ready
                else str(fallback["message"])
            ),
            "hosted_provider": hosted_provider,
        },
        tradeoffs=tradeoffs,
    )


def _probe_ollama(*, base_url: str, model: str, timeout_seconds: float) -> dict[str, object]:
    request = urlrequest.Request(f"{base_url}/api/tags", method="GET")
    try:
        with urlrequest.urlopen(request, timeout=timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (TimeoutError, socket.timeout):
        return {
            "status": "loading",
            "installed": False,
            "available_models": [],
            "message": "Ollama did not respond before the timeout; it may still be starting.",
        }
    except urlerror.URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            return {
                "status": "loading",
                "installed": False,
                "available_models": [],
                "message": "Ollama did not respond before the timeout; it may still be starting.",
            }
        return {
            "status": "unavailable",
            "installed": False,
            "available_models": [],
            "message": "Ollama is not reachable at the configured base URL.",
        }
    except (OSError, json.JSONDecodeError):
        return {
            "status": "unavailable",
            "installed": False,
            "available_models": [],
            "message": "Ollama responded, but the model list could not be read.",
        }

    available_models = _available_model_names(data)
    installed = _model_is_listed(data, model)
    if installed:
        return {
            "status": "ready",
            "installed": True,
            "available_models": available_models,
            "message": f"Local model {model} is installed and ready.",
        }
    return {
        "status": "unavailable",
        "installed": False,
        "available_models": available_models,
        "message": f"Ollama is running, but model {model} is not installed.",
    }


def _validate_local_base_url(base_url: str) -> str | None:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return "OLLAMA_BASE_URL must be an http(s) URL pointing to a local model runtime."
    hostname = parsed.hostname.lower()
    if hostname in {"localhost", "127.0.0.1", "::1"} or hostname.endswith(".local"):
        return None
    try:
        address = ip_address(hostname)
    except ValueError:
        return "OLLAMA_BASE_URL must point to a local or private-network model runtime, such as localhost, a .local hostname, or a private IP address."
    if address.is_private or address.is_loopback:
        return None
    return "OLLAMA_BASE_URL must point to a local or private-network model runtime."


def _available_model_names(data: dict[str, object]) -> list[str]:
    models = data.get("models")
    if not isinstance(models, list):
        return []
    names = []
    for item in models:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("model") or "")
        if name:
            names.append(name)
    return sorted(names)


def _model_is_listed(data: dict[str, object], model: str) -> bool:
    for name in _available_model_names(data):
        if name == model or name.startswith(f"{model}:"):
            return True
    return False

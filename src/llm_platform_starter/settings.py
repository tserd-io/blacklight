from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

USER_ENV_PATH_ENV = "LLM_PLATFORM_USER_ENV_PATH"
DEFAULT_USER_ENV_PATH = "user.env"

USER_EDITABLE_ENV_KEYS = {
    "LLM_PROVIDER",
    "LLM_MODEL",
    "TRACE_DB_PATH",
    "OPENAI_API_KEY",
    "LLM_CUSTOM_PROVIDER",
    "LLM_PROVIDER_TIMEOUT_SECONDS",
    "LLM_PROVIDER_MAX_RETRIES",
    "LLM_PROVIDER_RATE_LIMIT_REQUESTS",
    "LLM_PROVIDER_RATE_LIMIT_WINDOW_SECONDS",
}
SECRET_ENV_KEYS = {"OPENAI_API_KEY"}


@dataclass(frozen=True)
class Settings:
    provider: str = "mock"
    model: str = "mock-ticket-classifier"
    trace_db_path: str = "traces.sqlite3"
    openai_api_key: str | None = None
    custom_provider_path: str | None = None
    provider_timeout_seconds: float = 30.0
    provider_max_retries: int = 2
    provider_rate_limit_requests: int = 3
    provider_rate_limit_window_seconds: float = 10.0


def get_user_env_path(path: str | Path | None = None) -> Path:
    return Path(path or os.getenv(USER_ENV_PATH_ENV) or DEFAULT_USER_ENV_PATH)


def load_user_env(path: str | Path | None = None) -> dict[str, str]:
    user_env_path = get_user_env_path(path)
    if not user_env_path.exists():
        return {}
    values: dict[str, str] = {}
    for line in user_env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if not key:
            continue
        values[key] = _unquote_env_value(value.strip())
    return values


def write_user_env(
    updates: dict[str, Any],
    path: str | Path | None = None,
) -> dict[str, str]:
    unknown_keys = sorted(set(updates) - USER_EDITABLE_ENV_KEYS)
    if unknown_keys:
        raise ValueError(f"Unsupported user.env setting(s): {', '.join(unknown_keys)}")

    user_env_path = get_user_env_path(path)
    user_env_path.parent.mkdir(parents=True, exist_ok=True)
    existing_lines = (
        user_env_path.read_text(encoding="utf-8").splitlines()
        if user_env_path.exists()
        else []
    )
    remaining_updates = dict(updates)
    output_lines: list[str] = []
    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            output_lines.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key not in remaining_updates:
            output_lines.append(line)
            continue
        value = remaining_updates.pop(key)
        if value is not None:
            output_lines.append(f"{key}={_quote_env_value(value)}")

    for key in sorted(remaining_updates):
        value = remaining_updates[key]
        if value is not None:
            output_lines.append(f"{key}={_quote_env_value(value)}")

    temp_path = user_env_path.with_name(f"{user_env_path.name}.tmp")
    temp_path.write_text("\n".join(output_lines).rstrip() + "\n", encoding="utf-8")
    temp_path.replace(user_env_path)
    return load_user_env(user_env_path)


def load_settings(user_env_path: str | Path | None = None) -> Settings:
    user_env = load_user_env(user_env_path)
    return Settings(
        provider=_setting("LLM_PROVIDER", "mock", user_env),
        model=_setting("LLM_MODEL", "mock-ticket-classifier", user_env),
        trace_db_path=_setting("TRACE_DB_PATH", "traces.sqlite3", user_env),
        openai_api_key=_setting("OPENAI_API_KEY", "", user_env) or None,
        custom_provider_path=_setting("LLM_CUSTOM_PROVIDER", "", user_env) or None,
        provider_timeout_seconds=float(
            _setting("LLM_PROVIDER_TIMEOUT_SECONDS", "30", user_env)
        ),
        provider_max_retries=int(_setting("LLM_PROVIDER_MAX_RETRIES", "2", user_env)),
        provider_rate_limit_requests=int(
            _setting("LLM_PROVIDER_RATE_LIMIT_REQUESTS", "3", user_env)
        ),
        provider_rate_limit_window_seconds=float(
            _setting("LLM_PROVIDER_RATE_LIMIT_WINDOW_SECONDS", "10", user_env)
        ),
    )


def _setting(key: str, default: str, user_env: dict[str, str]) -> str:
    process_value = os.getenv(key)
    if process_value is not None:
        return process_value
    return user_env.get(key, default)


def _quote_env_value(value: Any) -> str:
    text = str(value)
    if not text or any(char.isspace() for char in text) or "#" in text or '"' in text:
        return json.dumps(text)
    return text


def _unquote_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        try:
            return json.loads(value) if value[0] == '"' else value[1:-1]
        except json.JSONDecodeError:
            return value[1:-1]
    return value

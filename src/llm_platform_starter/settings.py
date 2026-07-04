from __future__ import annotations

import os
from dataclasses import dataclass


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


def load_settings() -> Settings:
    return Settings(
        provider=os.getenv("LLM_PROVIDER", "mock"),
        model=os.getenv("LLM_MODEL", "mock-ticket-classifier"),
        trace_db_path=os.getenv("TRACE_DB_PATH", "traces.sqlite3"),
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        custom_provider_path=os.getenv("LLM_CUSTOM_PROVIDER") or None,
        provider_timeout_seconds=float(os.getenv("LLM_PROVIDER_TIMEOUT_SECONDS", "30")),
        provider_max_retries=int(os.getenv("LLM_PROVIDER_MAX_RETRIES", "2")),
        provider_rate_limit_requests=int(os.getenv("LLM_PROVIDER_RATE_LIMIT_REQUESTS", "3")),
        provider_rate_limit_window_seconds=float(
            os.getenv("LLM_PROVIDER_RATE_LIMIT_WINDOW_SECONDS", "10")
        ),
    )

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Header

from llm_platform_starter.examples.ticket_classifier import TicketClassifier
from llm_platform_starter.models import TicketClassification, TicketRequest
from llm_platform_starter.observability.idempotency import IdempotencyStore
from llm_platform_starter.observability.storage import TraceStore
from llm_platform_starter.providers.factory import create_provider
from llm_platform_starter.settings import load_settings

settings = load_settings()
trace_store = TraceStore(settings.trace_db_path)
idempotency_store = IdempotencyStore(settings.trace_db_path)
classifier = TicketClassifier(
    provider=create_provider(settings),
    model=settings.model,
    trace_store=trace_store,
    idempotency_store=idempotency_store,
    provider_timeout_seconds=settings.provider_timeout_seconds,
    provider_max_retries=settings.provider_max_retries,
    provider_rate_limit_requests=settings.provider_rate_limit_requests,
    provider_rate_limit_window_seconds=settings.provider_rate_limit_window_seconds,
)

app = FastAPI(title="LLM Platform Starter", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/classify-ticket")
def classify_ticket(
    ticket: TicketRequest,
    x_session_id: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None),
) -> TicketClassification:
    if x_session_id and not ticket.session_id:
        ticket = ticket.model_copy(update={"session_id": x_session_id})
    if idempotency_key and not ticket.idempotency_key:
        ticket = ticket.model_copy(update={"idempotency_key": idempotency_key})
    return classifier.classify(ticket)


@app.get("/metrics")
def metrics() -> dict[str, Any]:
    return trace_store.metrics()

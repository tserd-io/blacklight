from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse

from llm_platform_starter.errors import GuardrailValidationError, describe_exception
from llm_platform_starter.examples.ticket_classifier import TicketClassifier
from llm_platform_starter.models import TicketClassification, TicketRequest
from llm_platform_starter.observability.idempotency import (
    IdempotencyInProgressError,
    IdempotencyStore,
)
from llm_platform_starter.observability.storage import TraceStore
from llm_platform_starter.providers.factory import ProviderConfigurationError, create_provider
from llm_platform_starter.providers.reliability import ProviderCallError
from llm_platform_starter.settings import load_settings

settings = load_settings()
trace_store = TraceStore(settings.trace_db_path)
idempotency_store = IdempotencyStore(settings.trace_db_path)
classifier: TicketClassifier | None = None
classifier_startup_error: ProviderConfigurationError | None = None


def _build_classifier() -> TicketClassifier:
    return TicketClassifier(
        provider=create_provider(settings),
        model=settings.model,
        trace_store=trace_store,
        idempotency_store=idempotency_store,
        provider_timeout_seconds=settings.provider_timeout_seconds,
        provider_max_retries=settings.provider_max_retries,
        provider_rate_limit_requests=settings.provider_rate_limit_requests,
        provider_rate_limit_window_seconds=settings.provider_rate_limit_window_seconds,
    )


try:
    classifier = _build_classifier()
except ProviderConfigurationError as exc:
    classifier_startup_error = exc

app = FastAPI(title="LLM Platform Starter", version="0.1.0")


def _error_response(exc: Exception, status_code: int) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=describe_exception(exc).as_payload())


@app.exception_handler(ProviderConfigurationError)
def provider_configuration_error_handler(_request: Any, exc: ProviderConfigurationError) -> JSONResponse:
    return _error_response(exc, status_code=500)


@app.exception_handler(ProviderCallError)
def provider_call_error_handler(_request: Any, exc: ProviderCallError) -> JSONResponse:
    return _error_response(exc, status_code=503)


@app.exception_handler(IdempotencyInProgressError)
def idempotency_error_handler(_request: Any, exc: IdempotencyInProgressError) -> JSONResponse:
    return _error_response(exc, status_code=409)


@app.exception_handler(GuardrailValidationError)
def validation_error_handler(_request: Any, exc: GuardrailValidationError) -> JSONResponse:
    return _error_response(exc, status_code=422)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/classify-ticket")
def classify_ticket(
    ticket: TicketRequest,
    x_session_id: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None),
) -> TicketClassification:
    if classifier_startup_error is not None:
        raise classifier_startup_error
    if classifier is None:
        raise ProviderConfigurationError("Provider classifier is not configured.")
    if x_session_id and not ticket.session_id:
        ticket = ticket.model_copy(update={"session_id": x_session_id})
    if idempotency_key and not ticket.idempotency_key:
        ticket = ticket.model_copy(update={"idempotency_key": idempotency_key})
    return classifier.classify(ticket)


@app.get("/metrics")
def metrics() -> dict[str, Any]:
    return trace_store.metrics()

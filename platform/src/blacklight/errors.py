from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from blacklight.observability.idempotency import IdempotencyInProgressError
from blacklight.providers.factory import ProviderConfigurationError
from blacklight.providers.reliability import ProviderCallError


class GuardrailValidationError(ValueError):
    """Raised when provider output fails expected guardrail validation."""


@dataclass(frozen=True)
class ErrorDetail:
    category: str
    message: str
    likely_cause: str
    next_step: str

    def as_payload(self) -> dict[str, Any]:
        return {
            "error": {
                "category": self.category,
                "message": self.message,
                "likely_cause": self.likely_cause,
                "next_step": self.next_step,
            }
        }


def trace_not_found_error(trace_id: str) -> ErrorDetail:
    return ErrorDetail(
        category="trace_not_found",
        message=f"Trace not found: {trace_id}",
        likely_cause="No trace record exists for that request id in the selected SQLite database.",
        next_step="Run `blacklight trace list` with the same --trace-db-path and retry with a listed request_id.",
    )


def session_not_found_error(session_id: str) -> ErrorDetail:
    return ErrorDetail(
        category="session_not_found",
        message=f"Session not found: {session_id}",
        likely_cause="No trace records exist for that session id in the selected SQLite database.",
        next_step="Run `blacklight trace list` with the same --trace-db-path and retry with a listed session_id.",
    )


def agent_not_found_error(agent_id: str) -> ErrorDetail:
    return ErrorDetail(
        category="agent_not_found",
        message=f"Agent not found: {agent_id}",
        likely_cause="No packaged agent definition exists for that agent id.",
        next_step="Run `blacklight agents list` and retry with a listed agent_id.",
    )


def describe_exception(exc: Exception) -> ErrorDetail:
    if isinstance(exc, ProviderConfigurationError):
        return ErrorDetail(
            category="configuration_error",
            message=str(exc),
            likely_cause="Provider settings are missing, malformed, or incompatible with the selected provider.",
            next_step="Run `blacklight health` and check LLM_PROVIDER, OPENAI_API_KEY, or LLM_CUSTOM_PROVIDER.",
        )
    if isinstance(exc, ProviderCallError):
        return ErrorDetail(
            category=exc.category,
            message=str(exc),
            likely_cause=_provider_likely_cause(exc.category),
            next_step="Check provider credentials, endpoint availability, timeout, retry, and rate-limit settings.",
        )
    if isinstance(exc, IdempotencyInProgressError):
        return ErrorDetail(
            category="idempotency_in_progress",
            message=str(exc),
            likely_cause="Another request with the same idempotency key is still marked in progress.",
            next_step="Wait for the original request to finish or retry with a different idempotency key.",
        )
    if isinstance(exc, GuardrailValidationError):
        return ErrorDetail(
            category="validation_error",
            message=str(exc),
            likely_cause="The model output did not match the expected structured schema or guardrail checks.",
            next_step="Inspect the provider output and trace metadata, then adjust the prompt or provider response format.",
        )
    return ErrorDetail(
        category="unexpected_error",
        message=str(exc) or exc.__class__.__name__,
        likely_cause="An unhandled application error occurred.",
        next_step="Review the traceback in local logs and add a narrower error handler if this becomes a known failure mode.",
    )


def _provider_likely_cause(category: str) -> str:
    causes = {
        "provider_timeout": "The provider did not return before the configured timeout.",
        "provider_empty_response": "The provider returned null, empty, or whitespace-only output after retries.",
        "provider_error": "The provider adapter raised an error or the remote provider rejected the request.",
    }
    return causes.get(category, "The provider call failed.")


def is_known_error(exc: Exception) -> bool:
    return isinstance(
        exc,
        (
            GuardrailValidationError,
            IdempotencyInProgressError,
            ProviderCallError,
            ProviderConfigurationError,
        ),
    )

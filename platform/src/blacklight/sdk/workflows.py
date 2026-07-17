from __future__ import annotations

import uuid
from collections.abc import Mapping
from sqlite3 import Error as SQLiteError
from typing import Any, Literal

from pydantic import BaseModel, Field

from blacklight.errors import ErrorDetail, GuardrailValidationError, describe_exception
from blacklight.examples.ticket_classifier import TicketClassifier
from blacklight.models import TicketClassification, TicketRequest
from blacklight.observability.idempotency import IdempotencyInProgressError, IdempotencyStore
from blacklight.observability.storage import TraceStore
from blacklight.providers.base import LLMProvider
from blacklight.providers.reliability import ProviderCallError
from blacklight.review import (
    review_reason_for_guardrail_outcome,
    review_routing_decision,
    review_state_for_guardrail_outcome,
)
from blacklight.settings import Settings


def _storage_error_detail(exc: Exception) -> ErrorDetail:
    return ErrorDetail(
        category="storage_error",
        message=str(exc) or exc.__class__.__name__,
        likely_cause="Blacklight could not open or write to the configured trace database.",
        next_step="Check TRACE_DB_PATH, directory permissions, and whether another process is holding the SQLite database open.",
    )


class WorkflowDescriptor(BaseModel):
    workflow_id: str
    name: str
    input_model: str
    output_model: str


class WorkflowValidationResult(BaseModel):
    passed: bool
    guardrail_outcome: str
    error_category: str | None = None
    errors: list[str] = Field(default_factory=list)


class WorkflowReviewState(BaseModel):
    state: str
    required: bool
    reason: str
    routing_decision: str


class WorkflowTraceSummary(BaseModel):
    trace_id: str
    request_id: str
    session_id: str
    agent_run_id: str | None = None
    trace_db_path: str


class WorkflowError(BaseModel):
    category: str
    message: str
    likely_cause: str
    next_step: str

    @classmethod
    def from_detail(cls, detail: ErrorDetail) -> WorkflowError:
        return cls(
            category=detail.category,
            message=detail.message,
            likely_cause=detail.likely_cause,
            next_step=detail.next_step,
        )


class WorkflowResult(BaseModel):
    workflow_id: str
    workflow_run_id: str
    run_status: Literal["completed", "failed"]
    output: TicketClassification | None
    trace: WorkflowTraceSummary | None
    validation: WorkflowValidationResult
    guardrail: dict[str, Any]
    review: WorkflowReviewState
    error: WorkflowError | None = None
    provider: str
    model: str
    prompt_id: str
    prompt_version: int | None
    latency_ms: float
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float

    @property
    def trace_id(self) -> str | None:
        return self.trace.trace_id if self.trace else None


class WorkflowClient:
    def __init__(self, *, provider: LLMProvider, settings: Settings) -> None:
        self._provider = provider
        self._settings = settings

    def list(self) -> list[WorkflowDescriptor]:
        return [
            WorkflowDescriptor(
                workflow_id="ticket_classifier",
                name="Ticket Classifier",
                input_model="TicketRequest",
                output_model="TicketClassification",
            )
        ]

    def run(
        self,
        workflow_id: str,
        *,
        input: TicketRequest | Mapping[str, Any],
    ) -> WorkflowResult:
        if workflow_id != "ticket_classifier":
            raise ValueError(f"Unsupported workflow_id: {workflow_id}")
        ticket = input if isinstance(input, TicketRequest) else TicketRequest.model_validate(input)
        return self._run_ticket_classifier(ticket)

    def run_ticket_classifier(
        self,
        *,
        subject: str,
        body: str,
        session_id: str | None = None,
    ) -> WorkflowResult:
        return self._run_ticket_classifier(
            TicketRequest(subject=subject, body=body, session_id=session_id)
        )

    def _run_ticket_classifier(self, ticket: TicketRequest) -> WorkflowResult:
        workflow_run_id = f"workflow-run-{uuid.uuid4()}"
        session_id = ticket.session_id or workflow_run_id
        db_path = self._settings.trace_db_path
        try:
            trace_store = TraceStore(db_path)
            idempotency_store = IdempotencyStore(db_path)
        except (OSError, SQLiteError) as exc:
            return self._result_without_trace(
                workflow_run_id=workflow_run_id,
                error_detail=_storage_error_detail(exc),
                validation_errors=[str(exc) or exc.__class__.__name__],
            )
        classifier = TicketClassifier(
            provider=self._provider,
            model=self._settings.model,
            trace_store=trace_store,
            idempotency_store=idempotency_store,
            provider_timeout_seconds=self._settings.provider_timeout_seconds,
            provider_max_retries=self._settings.provider_max_retries,
            provider_rate_limit_requests=self._settings.provider_rate_limit_requests,
            provider_rate_limit_window_seconds=self._settings.provider_rate_limit_window_seconds,
        )
        run_ticket = ticket.model_copy(
            update={
                "session_id": session_id,
                "idempotency_key": workflow_run_id,
                "agent_run_id": workflow_run_id,
            }
        )
        error_detail: ErrorDetail | None = None
        validation_errors: list[str] = []
        output: TicketClassification | None
        try:
            output = classifier.classify(run_ticket)
        except (GuardrailValidationError, IdempotencyInProgressError, ProviderCallError) as exc:
            output = None
            error_detail = describe_exception(exc)
            validation_errors = [str(exc)]

        traces = trace_store.list_by_agent_run_id(workflow_run_id)
        if not traces:
            if error_detail:
                return self._result_without_trace(
                    workflow_run_id=workflow_run_id,
                    error_detail=error_detail,
                    validation_errors=validation_errors,
                )
            raise RuntimeError("Workflow run did not write a trace.")
        trace = traces[-1]
        return self._result_from_trace(
            workflow_run_id=workflow_run_id,
            output=output,
            trace=trace,
            validation_errors=validation_errors,
            error_detail=error_detail,
        )

    def _result_from_trace(
        self,
        *,
        workflow_run_id: str,
        output: TicketClassification | None,
        trace: dict[str, Any],
        validation_errors: list[str],
        error_detail: ErrorDetail | None,
    ) -> WorkflowResult:
        review_state = review_state_for_guardrail_outcome(trace["guardrail_outcome"])
        review_reason = review_reason_for_guardrail_outcome(
            trace["guardrail_outcome"],
            trace["error_category"],
        )
        return WorkflowResult(
            workflow_id="ticket_classifier",
            workflow_run_id=workflow_run_id,
            run_status="completed" if output is not None else "failed",
            output=output,
            trace=WorkflowTraceSummary(
                trace_id=trace["request_id"],
                request_id=trace["request_id"],
                session_id=trace["session_id"],
                agent_run_id=trace["agent_run_id"],
                trace_db_path=self._settings.trace_db_path,
            ),
            validation=WorkflowValidationResult(
                passed=trace["validation_passed"],
                guardrail_outcome=trace["guardrail_outcome"],
                error_category=trace["error_category"],
                errors=validation_errors,
            ),
            guardrail={
                "outcome": trace["guardrail_outcome"],
                "reason": review_reason,
                "error_category": trace["error_category"],
            },
            review=WorkflowReviewState(
                state=review_state,
                required=trace["guardrail_outcome"] in {"needs_review", "rejected"},
                reason=review_reason,
                routing_decision=review_routing_decision(review_state),
            ),
            error=WorkflowError.from_detail(error_detail) if error_detail else None,
            provider=trace["provider"],
            model=trace["model"],
            prompt_id=trace["prompt_id"],
            prompt_version=trace["prompt_version"],
            latency_ms=trace["latency_ms"],
            input_tokens=trace["input_tokens"],
            output_tokens=trace["output_tokens"],
            estimated_cost_usd=trace["estimated_cost_usd"],
        )

    def _result_without_trace(
        self,
        *,
        workflow_run_id: str,
        error_detail: ErrorDetail,
        validation_errors: list[str],
    ) -> WorkflowResult:
        review_state = "rejected"
        return WorkflowResult(
            workflow_id="ticket_classifier",
            workflow_run_id=workflow_run_id,
            run_status="failed",
            output=None,
            trace=None,
            validation=WorkflowValidationResult(
                passed=False,
                guardrail_outcome="rejected",
                error_category=error_detail.category,
                errors=validation_errors,
            ),
            guardrail={
                "outcome": "rejected",
                "reason": error_detail.likely_cause,
                "error_category": error_detail.category,
            },
            review=WorkflowReviewState(
                state=review_state,
                required=True,
                reason=error_detail.likely_cause,
                routing_decision=review_routing_decision(review_state),
            ),
            error=WorkflowError.from_detail(error_detail),
            provider=self._provider.name,
            model=self._settings.model,
            prompt_id=TicketClassifier.prompt_id,
            prompt_version=None,
            latency_ms=0,
            input_tokens=0,
            output_tokens=0,
            estimated_cost_usd=0,
        )

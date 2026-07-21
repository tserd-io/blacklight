from __future__ import annotations

import uuid
from collections.abc import Mapping
from sqlite3 import Error as SQLiteError
from typing import Any, Literal

from pydantic import BaseModel, Field

from blacklight.agents import AgentDefinition, AgentRegistry
from blacklight.agents.runs import build_agent_run_envelope, build_agent_run_payload
from blacklight.errors import ErrorDetail, GuardrailValidationError, describe_exception
from blacklight.examples.ticket_classifier import TicketClassifier
from blacklight.models import TicketClassification, TicketRequest
from blacklight.observability.agent_runs import AgentRunStore
from blacklight.observability.idempotency import IdempotencyInProgressError, IdempotencyStore
from blacklight.observability.storage import TraceStore
from blacklight.providers.base import LLMProvider
from blacklight.providers.reliability import ProviderCallError
from blacklight.review import review_routing_decision
from blacklight.sdk.errors import SDKNotFoundError, TypedError, storage_error_detail
from blacklight.session_history import trace_domain_to_range_detail
from blacklight.settings import Settings


class AgentSummary(BaseModel):
    agent_id: str
    display_name: str
    version: int
    active: bool
    workflow_id: str
    output_schema: str
    prompt_ids: list[str] = Field(default_factory=list)


class AgentListResult(BaseModel):
    agents: list[AgentSummary] = Field(default_factory=list)


class AgentProfile(BaseModel):
    agent: AgentDefinition
    domain: dict[str, Any]
    governed_range: dict[str, Any]
    trace_contract: dict[str, Any]


class AgentRunInput(BaseModel):
    subject: str
    body: str
    session_id: str | None = None
    verbose: bool = False
    context: dict[str, Any] | None = None
    insight: dict[str, Any] | str | None = None
    suggested_action: dict[str, Any] | str | None = None
    final_action: dict[str, Any] | str | None = None


class AgentRunError(TypedError):
    pass


class AgentRunResult(BaseModel):
    run_status: Literal["completed", "failed"]
    agent_run_id: str
    trace_id: str | None
    payload: dict[str, Any]
    envelope: dict[str, Any] | None
    domain_to_range: dict[str, Any] | None = None
    run_context: dict[str, Any] = Field(default_factory=dict)
    error: AgentRunError | None = None


class AgentClient:
    def __init__(self, *, provider: LLMProvider, settings: Settings) -> None:
        self._provider = provider
        self._settings = settings
        self._registry = AgentRegistry()

    def list(self) -> AgentListResult:
        return AgentListResult(
            agents=[
                AgentSummary(
                    agent_id=agent.agent_id,
                    display_name=agent.display_name,
                    version=agent.version,
                    active=agent.active,
                    workflow_id=agent.workflow_id,
                    output_schema=agent.governed_range.output_schema,
                    prompt_ids=agent.domain.prompt_ids,
                )
                for agent in self._registry.list()
            ]
        )

    def show(self, agent_id: str) -> AgentProfile:
        agent = self._get_agent(agent_id)
        return AgentProfile(
            agent=agent,
            domain=agent.domain.model_dump(mode="json"),
            governed_range=agent.governed_range.model_dump(mode="json"),
            trace_contract=agent.trace_contract.model_dump(mode="json"),
        )

    def run(
        self,
        agent_id: str,
        *,
        input: AgentRunInput | Mapping[str, Any],
    ) -> AgentRunResult:
        agent = self._get_agent(agent_id)
        self._assert_runnable_agent(agent)
        run_input = (
            input if isinstance(input, AgentRunInput) else AgentRunInput.model_validate(input)
        )
        return self._run_ticket_classifier_agent(agent=agent, run_input=run_input)

    def _get_agent(self, agent_id: str) -> AgentDefinition:
        agent = self._registry.get_optional(agent_id)
        if agent is None:
            raise SDKNotFoundError(f"Agent not found: {agent_id}")
        return agent

    @staticmethod
    def _assert_runnable_agent(agent: AgentDefinition) -> None:
        if agent.agent_id != "ticket_classifier_agent":
            raise ValueError(
                "Only ticket_classifier_agent is runnable through the SDK in this milestone: "
                f"{agent.agent_id}"
            )

    def _run_ticket_classifier_agent(
        self,
        *,
        agent: AgentDefinition,
        run_input: AgentRunInput,
    ) -> AgentRunResult:
        run_id = f"agent-run-{uuid.uuid4()}"
        requested_session_id = run_input.session_id
        session_id = requested_session_id or run_id
        db_path = self._settings.trace_db_path
        run_context = self._run_context_payload(run_input)
        try:
            trace_store = TraceStore(db_path)
            idempotency_store = IdempotencyStore(db_path)
            agent_run_store = AgentRunStore(db_path)
        except (OSError, SQLiteError) as exc:
            return self._result_without_trace(
                agent=agent,
                run_id=run_id,
                requested_session_id=requested_session_id,
                session_id=session_id,
                db_path=db_path,
                run_context=run_context,
                error_detail=storage_error_detail(exc),
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
        ticket = TicketRequest(
            subject=run_input.subject,
            body=run_input.body,
            session_id=session_id,
            idempotency_key=run_id,
            agent_run_id=run_id,
        )
        result: TicketClassification | None
        validation_errors: list[str] | None = None
        error_detail: ErrorDetail | None = None
        try:
            result = classifier.classify(ticket)
        except (GuardrailValidationError, IdempotencyInProgressError, ProviderCallError) as exc:
            result = None
            validation_errors = [str(exc)]
            error_detail = describe_exception(exc)

        traces = trace_store.list_by_agent_run_id(run_id)
        if not traces:
            if error_detail:
                return self._result_without_trace(
                    agent=agent,
                    run_id=run_id,
                    requested_session_id=requested_session_id,
                    session_id=session_id,
                    db_path=db_path,
                    run_context=run_context,
                    error_detail=error_detail,
                    validation_errors=validation_errors or [],
                )
            raise RuntimeError("Agent run did not write a trace.")
        trace = traces[-1]
        payload = build_agent_run_payload(
            agent=agent,
            run_id=run_id,
            requested_session_id=requested_session_id,
            session_id=session_id,
            db_path=db_path,
            result=result,
            trace=trace,
            verbose=run_input.verbose,
            validation_errors=validation_errors,
        )
        if run_context:
            payload["run_context"] = run_context
        envelope = build_agent_run_envelope(
            agent=agent,
            run_id=run_id,
            session_id=session_id,
            subject=run_input.subject,
            body=run_input.body,
            trace=trace,
            payload=payload,
        )
        if run_context:
            envelope["run_context"] = run_context
        try:
            agent_run_store.insert(envelope)
        except (OSError, SQLiteError) as exc:
            error = AgentRunError.from_detail(storage_error_detail(exc))
            payload["trace_envelope"] = envelope
            payload["error"] = error.model_dump(mode="json")
            domain_to_range = trace_domain_to_range_detail(trace, envelope)["domain_to_range"]
            return AgentRunResult(
                run_status="failed",
                agent_run_id=run_id,
                trace_id=trace["request_id"],
                payload=payload,
                envelope=envelope,
                domain_to_range=domain_to_range,
                run_context=run_context,
                error=error,
            )
        payload["trace_envelope"] = envelope
        error = AgentRunError.from_detail(error_detail) if error_detail else None
        if error:
            payload["error"] = error.model_dump(mode="json")
        domain_to_range = trace_domain_to_range_detail(trace, envelope)["domain_to_range"]
        return AgentRunResult(
            run_status=payload["agent_run"]["run_status"],
            agent_run_id=run_id,
            trace_id=trace["request_id"],
            payload=payload,
            envelope=envelope,
            domain_to_range=domain_to_range,
            run_context=run_context,
            error=error,
        )

    def _result_without_trace(
        self,
        *,
        agent: AgentDefinition,
        run_id: str,
        requested_session_id: str | None,
        session_id: str,
        db_path: str,
        run_context: dict[str, Any],
        error_detail: ErrorDetail,
        validation_errors: list[str],
    ) -> AgentRunResult:
        error = AgentRunError.from_detail(error_detail)
        payload: dict[str, Any] = {
            "agent_run": {
                "run_id": run_id,
                "agent_run_id": run_id,
                "agent_id": agent.agent_id,
                "agent_version": agent.version,
                "workflow_id": agent.workflow_id,
                "run_status": "failed",
                "session_id": session_id,
                "requested_session_id": requested_session_id,
            },
            "trace": {
                "trace_id": None,
                "request_id": None,
                "session_id": session_id,
                "agent_run_id": run_id,
                "trace_db_path": db_path,
                "session_linkage": (
                    "Trace evidence was not written, but session_id preserves the requested session."
                    if requested_session_id
                    else "Trace evidence was not written; the generated agent run ID is the session fallback."
                ),
            },
            "domain": agent.domain.model_dump(mode="json"),
            "governed_range": agent.governed_range.model_dump(mode="json"),
            "trace_contract": agent.trace_contract.model_dump(mode="json"),
            "validation": {
                "passed": False,
                "guardrail_outcome": "rejected",
                "review_state": "rejected",
                "review_required": True,
                "review_reason": error_detail.likely_cause,
                "routing_decision": review_routing_decision("rejected"),
                "error_category": error_detail.category,
                "errors": validation_errors,
            },
            "guardrail": {
                "outcome": "rejected",
                "reason": error_detail.likely_cause,
                "error_category": error_detail.category,
            },
            "review": {
                "state": "rejected",
                "required": True,
                "reason": error_detail.likely_cause,
                "routing_decision": review_routing_decision("rejected"),
                "queue_hint": "Show this run in review queues before downstream automation.",
            },
            "output_summary": None,
            "output": None,
            "run_context": run_context,
            "error": error.model_dump(mode="json"),
        }
        return AgentRunResult(
            run_status="failed",
            agent_run_id=run_id,
            trace_id=None,
            payload=payload,
            envelope=None,
            domain_to_range=None,
            run_context=run_context,
            error=error,
        )

    @staticmethod
    def _run_context_payload(run_input: AgentRunInput) -> dict[str, Any]:
        optional_fields = {
            "context": run_input.context,
            "insight": run_input.insight,
            "suggested_action": run_input.suggested_action,
            "final_action": run_input.final_action,
        }
        return {key: value for key, value in optional_fields.items() if value is not None}

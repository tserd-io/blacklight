import sqlite3

import pytest

from blacklight.examples.ticket_classifier import TicketClassifier
from blacklight.models import (
    GuardrailOutcome,
    ProviderRequest,
    ProviderResponse,
    TicketRequest,
    TraceRecord,
)
from blacklight.observability.storage import TraceStore
from blacklight.observability.agent_runs import AgentRunStore
from blacklight.providers.base import LLMProvider
from blacklight.providers.mock import MockProvider


class InvalidJsonProvider(LLMProvider):
    name = "invalid-json"

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        return ProviderResponse(
            text="not json",
            provider=self.name,
            model=request.model,
            input_tokens=1,
            output_tokens=2,
        )


def test_agent_run_store_persists_trace_envelope(tmp_path):
    store = AgentRunStore(tmp_path / "traces.sqlite3")
    envelope = {
        "agent_run_id": "agent-run-1",
        "agent_id": "ticket_classifier_agent",
        "agent_version": 1,
        "workflow_id": "ticket_classifier",
        "run_status": "completed",
        "session_id": "session-a",
        "trace_request_id": "trace-1",
        "trace_id": "trace-1",
        "domain_snapshot": {"prompt_ids": ["ticket_classifier"]},
        "context_bundle": {"raw_inputs_persisted": False},
        "provider_call": {"provider": "mock", "model": "mock-ticket-classifier"},
        "validation": {"passed": True, "errors": []},
        "guardrail": {"outcome": "accepted", "error_category": None},
        "range_output": {"output": {"category": "billing"}},
        "review": {"state": "accepted", "required": False},
        "eval_evidence": {"eval_run_id": None, "linked": False},
    }

    store.insert(envelope)
    stored = store.get("agent-run-1")
    recent = store.list_recent()
    session_runs = store.list_by_session_id("session-a")

    assert stored == envelope
    assert recent[0]["agent_run_id"] == "agent-run-1"
    assert recent[0]["trace_request_id"] == "trace-1"
    assert session_runs[0]["agent_run_id"] == "agent-run-1"


def test_ticket_classifier_writes_trace(tmp_path):
    store = TraceStore(tmp_path / "traces.sqlite3")
    classifier = TicketClassifier(
        provider=MockProvider(),
        model="mock-ticket-classifier",
        trace_store=store,
    )

    classifier.classify(
        TicketRequest(
            subject="Refund",
            body="Duplicate billing charge.",
            session_id="session-a",
        )
    )
    metrics = store.metrics()
    traces = store.list_recent()

    assert metrics["request_count"] == 1
    assert metrics["total_estimated_cost_usd"] == 0
    assert traces[0]["session_id"] == "session-a"
    assert traces[0]["guardrail_outcome"] == "accepted"


def test_ticket_classifier_writes_needs_review_guardrail_outcome(tmp_path):
    store = TraceStore(tmp_path / "traces.sqlite3")
    classifier = TicketClassifier(
        provider=MockProvider(),
        model="mock-ticket-classifier",
        trace_store=store,
    )

    classifier.classify(
        TicketRequest(
            subject="Account help",
            body="User email is test@example.com",
            session_id="session-a",
        )
    )
    traces = store.list_recent()

    assert traces[0]["validation_passed"] is False
    assert traces[0]["guardrail_outcome"] == "needs_review"


def test_ticket_classifier_writes_rejected_guardrail_outcome(tmp_path):
    store = TraceStore(tmp_path / "traces.sqlite3")
    classifier = TicketClassifier(
        provider=InvalidJsonProvider(),
        model="test-model",
        trace_store=store,
        provider_max_retries=0,
    )

    with pytest.raises(ValueError):
        classifier.classify(
            TicketRequest(
                subject="Refund",
                body="Duplicate billing charge.",
                session_id="session-a",
            )
        )
    traces = store.list_recent()

    assert traces[0]["validation_passed"] is False
    assert traces[0]["guardrail_outcome"] == "rejected"
    assert traces[0]["error_category"] == "validation_error"


def test_trace_store_records_eval_run_id(tmp_path):
    store = TraceStore(tmp_path / "traces.sqlite3")

    store.insert(
        TraceRecord(
            request_id="eval-run-1:billing_refund",
            session_id="session-a",
            eval_run_id="eval-run-1",
            prompt_id="ticket_classifier",
            prompt_version=1,
            provider="mock",
            model="mock-ticket-classifier",
            latency_ms=1.0,
            input_tokens=10,
            output_tokens=5,
            estimated_cost_usd=0.0,
            validation_passed=True,
            guardrail_outcome=GuardrailOutcome.needs_review,
        )
    )

    trace = store.get_by_request_id("eval-run-1:billing_refund")

    assert trace is not None
    assert trace["session_id"] == "session-a"
    assert trace["eval_run_id"] == "eval-run-1"
    assert trace["guardrail_outcome"] == "needs_review"


def test_trace_store_records_agent_run_id(tmp_path):
    store = TraceStore(tmp_path / "traces.sqlite3")

    store.insert(
        TraceRecord(
            request_id="request-1",
            session_id="session-a",
            agent_run_id="agent-run-1",
            prompt_id="ticket_classifier",
            prompt_version=1,
            provider="mock",
            model="mock-ticket-classifier",
            latency_ms=1.0,
            input_tokens=10,
            output_tokens=5,
            estimated_cost_usd=0.0,
            validation_passed=True,
            guardrail_outcome=GuardrailOutcome.accepted,
        )
    )

    trace = store.get_by_request_id("request-1")
    run_traces = store.list_by_agent_run_id("agent-run-1")

    assert trace is not None
    assert trace["session_id"] == "session-a"
    assert trace["agent_run_id"] == "agent-run-1"
    assert run_traces[0]["request_id"] == "request-1"


def test_trace_store_adds_new_trace_columns_to_existing_tables(tmp_path):
    db_path = tmp_path / "traces.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE traces (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              created_at TEXT DEFAULT CURRENT_TIMESTAMP,
              request_id TEXT NOT NULL,
              prompt_id TEXT NOT NULL,
              prompt_version INTEGER NOT NULL,
              provider TEXT NOT NULL,
              model TEXT NOT NULL,
              latency_ms REAL NOT NULL,
              input_tokens INTEGER NOT NULL,
              output_tokens INTEGER NOT NULL,
              estimated_cost_usd REAL NOT NULL,
              validation_passed INTEGER NOT NULL,
              error_category TEXT
            )
            """
        )

    store = TraceStore(db_path)
    store.insert(
        TraceRecord(
            request_id="request-1",
            session_id="session-a",
            prompt_id="ticket_classifier",
            prompt_version=1,
            provider="mock",
            model="mock-ticket-classifier",
            latency_ms=10,
            input_tokens=10,
            output_tokens=5,
            estimated_cost_usd=0.0,
            validation_passed=False,
            guardrail_outcome=GuardrailOutcome.rejected,
            error_category="validation_error",
        )
    )

    with sqlite3.connect(db_path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(traces)").fetchall()}
    trace = store.get_by_request_id("request-1")

    assert "guardrail_outcome" in columns
    assert "agent_run_id" in columns
    assert trace is not None
    assert trace["guardrail_outcome"] == "rejected"
    assert trace["agent_run_id"] is None


def test_trace_store_metrics_group_by_provider_and_model(tmp_path):
    store = TraceStore(tmp_path / "traces.sqlite3")

    store.insert(
        TraceRecord(
            request_id="request-1",
            session_id="session-a",
            prompt_id="ticket_classifier",
            prompt_version=1,
            provider="mock",
            model="mock-ticket-classifier",
            latency_ms=10,
            input_tokens=10,
            output_tokens=5,
            estimated_cost_usd=0.0,
            validation_passed=True,
            guardrail_outcome=GuardrailOutcome.accepted,
        )
    )
    store.insert(
        TraceRecord(
            request_id="request-2",
            session_id="session-a",
            prompt_id="ticket_classifier",
            prompt_version=1,
            provider="mock",
            model="mock-ticket-classifier",
            latency_ms=30,
            input_tokens=12,
            output_tokens=6,
            estimated_cost_usd=0.0,
            validation_passed=False,
            guardrail_outcome=GuardrailOutcome.rejected,
            error_category="validation_error",
        )
    )
    store.insert(
        TraceRecord(
            request_id="request-3",
            session_id="session-b",
            prompt_id="ticket_classifier",
            prompt_version=1,
            provider="openai",
            model="gpt-4.1-mini",
            latency_ms=50,
            input_tokens=20,
            output_tokens=10,
            estimated_cost_usd=0.000024,
            validation_passed=True,
            guardrail_outcome=GuardrailOutcome.needs_review,
            error_category="provider_timeout",
        )
    )

    metrics = store.metrics()

    assert metrics["request_count"] == 3
    assert metrics["avg_latency_ms"] == 30
    assert metrics["total_estimated_cost_usd"] == 0.000024
    assert metrics["failure_rate"] == 0.6667
    assert metrics["validation_failure_rate"] == 0.3333
    assert metrics["by_provider"] == [
        {
            "provider": "mock",
            "request_count": 2,
            "avg_latency_ms": 20,
            "total_estimated_cost_usd": 0.0,
            "failure_rate": 0.5,
            "validation_failure_rate": 0.5,
        },
        {
            "provider": "openai",
            "request_count": 1,
            "avg_latency_ms": 50,
            "total_estimated_cost_usd": 0.000024,
            "failure_rate": 1.0,
            "validation_failure_rate": 0.0,
        },
    ]
    assert metrics["by_model"][0]["model"] == "mock-ticket-classifier"
    assert metrics["by_provider_model"][0]["provider"] == "mock"
    assert metrics["by_provider_model"][0]["model"] == "mock-ticket-classifier"
    assert metrics["by_guardrail_outcome"] == [
        {
            "guardrail_outcome": "accepted",
            "request_count": 1,
            "avg_latency_ms": 10,
            "total_estimated_cost_usd": 0.0,
            "failure_rate": 0.0,
            "validation_failure_rate": 0.0,
        },
        {
            "guardrail_outcome": "needs_review",
            "request_count": 1,
            "avg_latency_ms": 50,
            "total_estimated_cost_usd": 0.000024,
            "failure_rate": 1.0,
            "validation_failure_rate": 0.0,
        },
        {
            "guardrail_outcome": "rejected",
            "request_count": 1,
            "avg_latency_ms": 30,
            "total_estimated_cost_usd": 0.0,
            "failure_rate": 1.0,
            "validation_failure_rate": 1.0,
        },
    ]


def test_trace_store_lists_by_session_id(tmp_path):
    store = TraceStore(tmp_path / "traces.sqlite3")

    for index, session_id in enumerate(["session-a", "session-b", "session-a"], start=1):
        store.insert(
            TraceRecord(
                request_id=f"request-{index}",
                session_id=session_id,
                prompt_id="ticket_classifier",
                prompt_version=1,
                provider="mock",
                model="mock-ticket-classifier",
                latency_ms=10,
                input_tokens=10,
                output_tokens=5,
                estimated_cost_usd=0.0,
                validation_passed=True,
            )
        )

    traces = store.list_by_session_id("session-a")

    assert [trace["request_id"] for trace in traces] == ["request-1", "request-3"]
    assert all(trace["session_id"] == "session-a" for trace in traces)

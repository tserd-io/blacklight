from llm_platform_starter.examples.ticket_classifier import TicketClassifier
from llm_platform_starter.models import TicketRequest, TraceRecord
from llm_platform_starter.observability.storage import TraceStore
from llm_platform_starter.providers.mock import MockProvider


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
        )
    )

    trace = store.get_by_request_id("eval-run-1:billing_refund")

    assert trace is not None
    assert trace["session_id"] == "session-a"
    assert trace["eval_run_id"] == "eval-run-1"


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

    assert [trace["request_id"] for trace in traces] == ["request-3", "request-1"]
    assert all(trace["session_id"] == "session-a" for trace in traces)

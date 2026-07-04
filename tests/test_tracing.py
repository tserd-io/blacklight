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

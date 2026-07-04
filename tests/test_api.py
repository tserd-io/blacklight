from fastapi.testclient import TestClient

from llm_platform_starter import api
from llm_platform_starter.models import GuardrailOutcome, TraceRecord
from llm_platform_starter.observability.storage import TraceStore


def test_metrics_endpoint_returns_expanded_trace_metrics(tmp_path):
    original_trace_store = api.trace_store
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
            validation_passed=False,
            guardrail_outcome=GuardrailOutcome.rejected,
            error_category="validation_error",
        )
    )
    api.trace_store = store

    try:
        response = TestClient(api.app).get("/metrics")
    finally:
        api.trace_store = original_trace_store

    payload = response.json()

    assert response.status_code == 200
    assert payload["request_count"] == 1
    assert payload["failure_rate"] == 1.0
    assert payload["validation_failure_rate"] == 1.0
    assert payload["by_provider"][0]["provider"] == "mock"
    assert payload["by_model"][0]["model"] == "mock-ticket-classifier"
    assert payload["by_provider_model"][0]["provider"] == "mock"
    assert payload["by_guardrail_outcome"][0]["guardrail_outcome"] == "rejected"

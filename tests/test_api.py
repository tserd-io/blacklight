import importlib
from dataclasses import replace

from fastapi.testclient import TestClient

from llm_platform_starter import api
from llm_platform_starter.demo_seed import seed_demo_data
from llm_platform_starter.errors import GuardrailValidationError
from llm_platform_starter.models import GuardrailOutcome, TraceRecord
from llm_platform_starter.observability.evaluations import EvalMetricStore
from llm_platform_starter.observability.reviews import ReviewDecisionStore
from llm_platform_starter.observability.storage import TraceStore
from llm_platform_starter.providers.factory import ProviderConfigurationError
from llm_platform_starter.providers.reliability import ProviderCallError


class ValidationFailureClassifier:
    def classify(self, _ticket):
        raise GuardrailValidationError("missing required field: category")


class ProviderFailureClassifier:
    def classify(self, _ticket):
        raise ProviderCallError(
            "Provider call failed after 3 attempt(s): timed out",
            category="provider_timeout",
            attempts=3,
        )


def _build_session_history_store(tmp_path):
    store = TraceStore(tmp_path / "traces.sqlite3")
    records = [
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
        ),
        TraceRecord(
            request_id="request-2",
            session_id="session-a",
            prompt_id="ticket_classifier",
            prompt_version=2,
            provider="openai",
            model="gpt-4.1-mini",
            latency_ms=25,
            input_tokens=20,
            output_tokens=7,
            estimated_cost_usd=0.00003,
            validation_passed=True,
            guardrail_outcome=GuardrailOutcome.needs_review,
        ),
        TraceRecord(
            request_id="request-3",
            session_id="session-a",
            prompt_id="ticket_classifier",
            prompt_version=2,
            provider="openai",
            model="gpt-4.1-mini",
            latency_ms=30,
            input_tokens=12,
            output_tokens=6,
            estimated_cost_usd=0.00002,
            validation_passed=False,
            guardrail_outcome=GuardrailOutcome.rejected,
        ),
        TraceRecord(
            request_id="request-4",
            session_id="session-a",
            prompt_id="ticket_classifier",
            prompt_version=2,
            provider="custom",
            model="local-model",
            latency_ms=40,
            input_tokens=8,
            output_tokens=0,
            estimated_cost_usd=0.0,
            validation_passed=False,
            guardrail_outcome=GuardrailOutcome.accepted,
            error_category="provider_timeout",
        ),
        TraceRecord(
            request_id="request-other",
            session_id="session-b",
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
        ),
    ]
    for record in records:
        store.insert(record)
    return store


def _patch_review_stores(monkeypatch, tmp_path):
    trace_store = _build_session_history_store(tmp_path)
    review_store = ReviewDecisionStore(tmp_path / "traces.sqlite3")
    monkeypatch.setattr(api, "trace_store", trace_store)
    monkeypatch.setattr(api, "review_store", review_store)
    return trace_store, review_store


def _patch_seeded_console_stores(monkeypatch, tmp_path):
    db_path = tmp_path / "console.sqlite3"
    seed_demo_data(str(db_path))
    trace_store = TraceStore(db_path)
    eval_store = EvalMetricStore(db_path)
    review_store = ReviewDecisionStore(db_path)
    monkeypatch.setattr(api, "trace_store", trace_store)
    monkeypatch.setattr(api, "eval_store", eval_store)
    monkeypatch.setattr(api, "review_store", review_store)
    monkeypatch.setattr(api, "settings", replace(api.settings, trace_db_path=str(db_path)))
    return trace_store, eval_store, review_store


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


def test_console_dashboard_exposes_demo_and_recent_inspection_links(monkeypatch, tmp_path):
    _patch_seeded_console_stores(monkeypatch, tmp_path)

    response = TestClient(api.app).get("/console")

    assert response.status_code == 200
    assert "Blacklight Studio" in response.text
    assert "Run Demo" in response.text
    assert "/console/workflows" in response.text
    assert "/console/traces" in response.text
    assert "/console/evals" in response.text
    assert "/console/review" in response.text
    assert "seed-demo:billing-success" in response.text
    assert "seed-demo-eval" in response.text
    assert "llm-platform demo --verbose" in response.text
    assert "llm-platform seed demo-data" in response.text


def test_console_surfaces_render_navigation_and_cli_equivalents(monkeypatch, tmp_path):
    _patch_seeded_console_stores(monkeypatch, tmp_path)
    client = TestClient(api.app)
    expected = {
        "/console/workflows": "llm-platform classify",
        "/console/runs": "llm-platform session show",
        "/console/traces": "llm-platform trace list",
        "/console/evals": "llm-platform eval list",
        "/console/prompts": "llm-platform prompts list",
        "/console/providers": "llm-platform health",
        "/console/review": "Review Queue",
        "/console/settings": "llm-platform health",
        "/console/docs": "Docs And Recipes",
    }

    for path, expected_text in expected.items():
        response = client.get(path)
        assert response.status_code == 200
        assert "Blacklight Studio" in response.text
        assert expected_text in response.text


def test_console_run_demo_links_result_to_trace_and_session(monkeypatch, tmp_path):
    trace_store, _eval_store, _review_store = _patch_seeded_console_stores(monkeypatch, tmp_path)

    response = TestClient(api.app).post("/console/run-demo")
    traces = trace_store.list_by_session_id("console-demo", limit=10)

    assert response.status_code == 200
    assert "Demo Result" in response.text
    assert "billing" in response.text
    assert "/sessions/console-demo" in response.text
    assert "llm-platform trace show" in response.text
    assert len(traces) == 1
    assert traces[0]["session_id"] == "console-demo"


def test_session_history_json_returns_filtered_session_timeline(monkeypatch, tmp_path):
    monkeypatch.setattr(api, "trace_store", _build_session_history_store(tmp_path))

    response = TestClient(api.app).get("/api/sessions/session-a?status=needs_review")
    payload = response.json()

    assert response.status_code == 200
    assert payload["session_id"] == "session-a"
    assert payload["status_filter"] == "needs_review"
    assert payload["summary"]["request_count"] == 4
    assert payload["summary"]["total_tokens"] == 68
    assert payload["summary"]["total_estimated_cost_usd"] == 0.00005
    assert payload["summary"]["failure_count"] == 1
    assert payload["summary"]["review_count"] == 1
    assert payload["filtered_summary"]["request_count"] == 1
    assert [trace["request_id"] for trace in payload["traces"]] == ["request-2"]
    assert payload["traces"][0]["status"] == "needs_review"
    assert payload["traces"][0]["review_url"] == "/sessions/session-a/review/request-2"


def test_session_history_json_filters_failed_requests(monkeypatch, tmp_path):
    monkeypatch.setattr(api, "trace_store", _build_session_history_store(tmp_path))

    response = TestClient(api.app).get("/api/sessions/session-a?status=failed")
    payload = response.json()

    assert response.status_code == 200
    assert [trace["request_id"] for trace in payload["traces"]] == ["request-4"]
    assert payload["traces"][0]["failure_reason"] == "provider_timeout"


def test_session_history_page_shows_cost_status_and_review_links(monkeypatch, tmp_path):
    monkeypatch.setattr(api, "trace_store", _build_session_history_store(tmp_path))

    response = TestClient(api.app).get("/sessions/session-a")

    assert response.status_code == 200
    assert "Session session-a" in response.text
    assert "$0.00005000" in response.text
    assert "Needs Review" in response.text
    assert "Provider Timeout" in response.text
    assert "mock-ticket-classifier" in response.text
    assert "gpt-4.1-mini" in response.text
    assert 'href="/sessions/session-a/review/request-2"' in response.text


def test_session_review_page_shows_reviewable_trace(monkeypatch, tmp_path):
    monkeypatch.setattr(api, "trace_store", _build_session_history_store(tmp_path))

    response = TestClient(api.app).get("/sessions/session-a/review/request-2")

    assert response.status_code == 200
    assert "Review Trace" in response.text
    assert "request-2" in response.text
    assert "needs_review" in response.text


def test_session_review_page_rejects_non_reviewable_trace(monkeypatch, tmp_path):
    monkeypatch.setattr(api, "trace_store", _build_session_history_store(tmp_path))

    response = TestClient(api.app).get("/sessions/session-a/review/request-1")

    assert response.status_code == 404


def test_session_history_missing_session_returns_structured_error(monkeypatch, tmp_path):
    monkeypatch.setattr(api, "trace_store", _build_session_history_store(tmp_path))

    response = TestClient(api.app).get("/api/sessions/missing-session")
    payload = response.json()

    assert response.status_code == 404
    assert payload["detail"]["category"] == "session_not_found"
    assert payload["detail"]["message"] == "Session not found: missing-session"


def test_session_history_rejects_unknown_filter(monkeypatch, tmp_path):
    monkeypatch.setattr(api, "trace_store", _build_session_history_store(tmp_path))

    response = TestClient(api.app).get("/api/sessions/session-a?status=unknown")

    assert response.status_code == 400
    assert "Unknown session status filter" in response.json()["detail"]


def test_review_queue_json_lists_pending_reviewable_outputs(monkeypatch, tmp_path):
    _trace_store, _review_store = _patch_review_stores(monkeypatch, tmp_path)

    response = TestClient(api.app).get("/api/reviews")
    payload = response.json()

    assert response.status_code == 200
    assert payload["summary"]["item_count"] == 2
    assert payload["summary"]["pending_count"] == 2
    assert payload["summary"]["blocked_count"] == 2
    assert [item["request_id"] for item in payload["items"]] == ["request-3", "request-2"]
    assert payload["items"][0]["review_status"] == "pending"
    assert payload["items"][0]["downstream_blocked"] is True
    assert "rejected" in payload["items"][0]["review_reason"].lower()
    assert "human review" in payload["items"][1]["review_reason"].lower()


def test_review_queue_page_shows_review_actions(monkeypatch, tmp_path):
    _trace_store, _review_store = _patch_review_stores(monkeypatch, tmp_path)

    response = TestClient(api.app).get("/reviews")

    assert response.status_code == 200
    assert "Business Review Queue" in response.text
    assert "request-2" in response.text
    assert "request-3" in response.text
    assert "Approve" in response.text
    assert "Reject" in response.text
    assert "Needs More Info" in response.text
    assert "Blocked" in response.text


def test_review_decision_json_persists_auditable_decision(monkeypatch, tmp_path):
    _trace_store, review_store = _patch_review_stores(monkeypatch, tmp_path)

    response = TestClient(api.app).post(
        "/api/reviews/request-2",
        json={
            "decision": "approved",
            "reviewer": "Avery",
            "notes": "Synthetic billing ticket is safe to automate.",
        },
    )
    payload = response.json()
    stored = review_store.get("request-2")

    assert response.status_code == 200
    assert payload["decision"]["decision"] == "approved"
    assert payload["downstream_blocked"] is False
    assert stored["reviewer"] == "Avery"
    assert stored["notes"] == "Synthetic billing ticket is safe to automate."

    queue_response = TestClient(api.app).get("/api/reviews")
    queue_payload = queue_response.json()
    assert [item["request_id"] for item in queue_payload["items"]] == ["request-3"]

    decided_response = TestClient(api.app).get("/api/reviews?include_decided=true")
    decided_payload = decided_response.json()
    approved_item = next(item for item in decided_payload["items"] if item["request_id"] == "request-2")
    assert approved_item["review_status"] == "approved"
    assert approved_item["downstream_blocked"] is False


def test_review_decision_page_form_persists_rejection(monkeypatch, tmp_path):
    _trace_store, review_store = _patch_review_stores(monkeypatch, tmp_path)

    response = TestClient(api.app).post(
        "/reviews/request-3",
        data={
            "decision": "rejected",
            "reviewer": "Morgan",
            "notes": "Rejected output stays blocked.",
        },
        follow_redirects=False,
    )
    stored = review_store.get("request-3")

    assert response.status_code == 303
    assert response.headers["location"] == "/reviews?include_decided=true"
    assert stored["decision"] == "rejected"
    assert stored["reviewer"] == "Morgan"
    assert stored["notes"] == "Rejected output stays blocked."


def test_review_decision_rejects_non_reviewable_trace(monkeypatch, tmp_path):
    _trace_store, _review_store = _patch_review_stores(monkeypatch, tmp_path)

    response = TestClient(api.app).post(
        "/api/reviews/request-1",
        json={"decision": "approved"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Trace is not reviewable."


def test_review_decision_rejects_unknown_decision(monkeypatch, tmp_path):
    _trace_store, _review_store = _patch_review_stores(monkeypatch, tmp_path)

    response = TestClient(api.app).post(
        "/api/reviews/request-2",
        json={"decision": "escalated"},
    )

    assert response.status_code == 400
    assert "Unknown review decision" in response.json()["detail"]


def test_classify_endpoint_returns_structured_validation_errors():
    original_classifier = api.classifier
    original_startup_error = api.classifier_startup_error
    api.classifier = ValidationFailureClassifier()
    api.classifier_startup_error = None

    try:
        response = TestClient(api.app).post(
            "/classify-ticket",
            json={"subject": "Refund", "body": "Duplicate charge"},
        )
    finally:
        api.classifier = original_classifier
        api.classifier_startup_error = original_startup_error

    payload = response.json()

    assert response.status_code == 422
    assert payload["error"]["category"] == "validation_error"
    assert payload["error"]["message"] == "missing required field: category"
    assert "schema" in payload["error"]["likely_cause"]
    assert "provider output" in payload["error"]["next_step"]


def test_classify_endpoint_returns_structured_provider_errors():
    original_classifier = api.classifier
    original_startup_error = api.classifier_startup_error
    api.classifier = ProviderFailureClassifier()
    api.classifier_startup_error = None

    try:
        response = TestClient(api.app).post(
            "/classify-ticket",
            json={"subject": "Refund", "body": "Duplicate charge"},
        )
    finally:
        api.classifier = original_classifier
        api.classifier_startup_error = original_startup_error

    payload = response.json()

    assert response.status_code == 503
    assert payload["error"]["category"] == "provider_timeout"
    assert "Provider call failed" in payload["error"]["message"]
    assert "timeout" in payload["error"]["likely_cause"]
    assert "provider credentials" in payload["error"]["next_step"]


def test_classify_endpoint_returns_structured_configuration_errors():
    original_classifier = api.classifier
    original_startup_error = api.classifier_startup_error
    api.classifier = None
    api.classifier_startup_error = ProviderConfigurationError("OPENAI_API_KEY is required.")

    try:
        response = TestClient(api.app).post(
            "/classify-ticket",
            json={"subject": "Refund", "body": "Duplicate charge"},
        )
    finally:
        api.classifier = original_classifier
        api.classifier_startup_error = original_startup_error

    payload = response.json()

    assert response.status_code == 500
    assert payload["error"]["category"] == "configuration_error"
    assert payload["error"]["message"] == "OPENAI_API_KEY is required."
    assert "Provider settings" in payload["error"]["likely_cause"]
    assert "llm-platform health" in payload["error"]["next_step"]


def test_api_import_keeps_app_available_when_provider_configuration_fails(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    try:
        reloaded_api = importlib.reload(api)
        response = TestClient(reloaded_api.app).post(
            "/classify-ticket",
            json={"subject": "Refund", "body": "Duplicate charge"},
        )
    finally:
        monkeypatch.setenv("LLM_PROVIDER", "mock")
        importlib.reload(api)

    payload = response.json()

    assert response.status_code == 500
    assert payload["error"]["category"] == "configuration_error"
    assert "OPENAI_API_KEY" in payload["error"]["message"]

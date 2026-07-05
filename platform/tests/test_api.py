import importlib
import shlex
from dataclasses import replace

from fastapi.testclient import TestClient

from blacklight import api
from blacklight.cli import build_parser
from blacklight.demo_seed import seed_demo_data
from blacklight.errors import GuardrailValidationError
from blacklight.models import GuardrailOutcome, TraceRecord
from blacklight.observability.evaluations import EvalMetricStore
from blacklight.observability.reviews import ReviewDecisionStore
from blacklight.observability.storage import TraceStore
from blacklight.providers.factory import ProviderConfigurationError
from blacklight.providers.reliability import ProviderCallError


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


def _assert_cli_command_parseable(command: str) -> None:
    assert command.startswith("blacklight ")
    assert "<" not in command
    assert ">" not in command
    build_parser().parse_args(shlex.split(command)[1:])


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
    assert "blacklight demo --verbose" in response.text
    assert "blacklight seed demo-data" in response.text


def test_console_surfaces_render_navigation_and_cli_equivalents(monkeypatch, tmp_path):
    _patch_seeded_console_stores(monkeypatch, tmp_path)
    client = TestClient(api.app)
    expected = {
        "/console/workflows": "blacklight classify",
        "/console/runs": "blacklight session show",
        "/console/traces": "blacklight trace list",
        "/console/evals": "blacklight eval list",
        "/console/prompts": "blacklight prompts list",
        "/console/providers": "blacklight health",
        "/console/review": "Review Queue",
        "/console/settings": "blacklight health",
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
    assert "blacklight trace show" in response.text
    assert len(traces) == 1
    assert traces[0]["session_id"] == "console-demo"


def test_console_api_dashboard_returns_first_run_state(monkeypatch, tmp_path):
    _patch_seeded_console_stores(monkeypatch, tmp_path)

    response = TestClient(api.app).get("/api/dashboard")
    payload = response.json()

    assert response.status_code == 200
    assert payload["metrics"]["request_count"] >= 5
    assert payload["recent_traces"]
    assert payload["recent_eval_runs"][0]["eval_run_id"] == "seed-demo-eval"
    assert payload["review_queue"]["pending_count"] >= 1
    assert payload["workflows"][0]["workflow_id"] == "ticket_classifier"
    assert payload["providers"][0]["provider"] == "mock"
    assert payload["settings"]["trace_db_path"].endswith("console.sqlite3")
    assert "blacklight demo --verbose" in payload["cli"]["guided_demo"]
    assert "blacklight seed demo-data" in payload["cli"]["seed_demo_data"]


def test_console_api_workflow_run_returns_result_trace_and_cli(monkeypatch, tmp_path):
    trace_store, _eval_store, _review_store = _patch_seeded_console_stores(monkeypatch, tmp_path)

    response = TestClient(api.app).post(
        "/api/console/workflows/ticket_classifier/run",
        json={
            "subject": "Refund request",
            "body": "Customer asks for a refund after duplicate billing.",
            "session_id": "api-workflow",
        },
    )
    payload = response.json()
    traces = trace_store.list_by_session_id("api-workflow", limit=10)

    assert response.status_code == 200
    assert payload["workflow_id"] == "ticket_classifier"
    assert payload["result"]["category"] == "billing"
    assert payload["trace"]["session_id"] == "api-workflow"
    assert payload["trace"]["links"]["session_api"] == "/api/sessions/api-workflow"
    assert payload["cli_command"] == payload["cli_commands"]["primary"]
    assert "blacklight classify" in payload["cli"]["equivalent_run"]
    assert "blacklight trace show" in payload["cli"]["trace"]
    _assert_cli_command_parseable(payload["cli_command"])
    _assert_cli_command_parseable(payload["cli_commands"]["trace"])
    assert len(traces) == 1


def test_console_api_surfaces_return_state_and_cli(monkeypatch, tmp_path):
    _patch_seeded_console_stores(monkeypatch, tmp_path)
    client = TestClient(api.app)
    endpoints = [
        ("/api/console/workflows", "workflows"),
        ("/api/console/workflows/ticket_classifier", "workflow"),
        ("/api/console/runs", "runs"),
        ("/api/console/runs/seed-demo", "traces"),
        ("/api/console/traces", "traces"),
        ("/api/console/traces/seed-demo:billing-success", "trace"),
        ("/api/console/evals", "eval_runs"),
        ("/api/console/evals/seed-demo-eval", "eval_run"),
        ("/api/console/prompts", "prompts"),
        ("/api/console/prompts/ticket_classifier", "prompt"),
        ("/api/console/providers", "providers"),
        ("/api/console/reviews", "items"),
        ("/api/console/settings", "provider"),
    ]

    for path, expected_key in endpoints:
        response = client.get(path)
        payload = response.json()

        assert response.status_code == 200
        assert expected_key in payload
        assert "cli_command" in payload
        assert "cli_commands" in payload
        assert "cli" in payload
        assert payload["cli_command"] == payload["cli_commands"]["primary"]
        _assert_cli_command_parseable(payload["cli_command"])


def test_console_api_eval_run_uses_mock_mode_and_persists_links(monkeypatch, tmp_path):
    _trace_store, eval_store, _review_store = _patch_seeded_console_stores(monkeypatch, tmp_path)

    response = TestClient(api.app).post(
        "/api/console/evals/run",
        json={"session_id": "api-eval"},
    )
    payload = response.json()
    eval_run_id = payload["eval_run"]["eval_run_id"]
    stored = eval_store.get_run(eval_run_id)

    assert response.status_code == 200
    assert payload["message"].startswith("Mock-mode eval completed")
    assert payload["eval_run"]["session_id"] == "api-eval"
    assert payload["eval_run"]["summary"]["case_count"] == 3
    assert len(payload["traces"]) == 3
    assert payload["traces"][0]["eval_run_id"] == eval_run_id
    assert payload["cli_command"] == payload["cli_commands"]["run"]
    assert "blacklight eval show" in payload["cli"]["show"]
    _assert_cli_command_parseable(payload["cli_commands"]["show"])
    assert stored is not None
    assert stored["session_id"] == "api-eval"


def test_console_api_provider_test_does_not_require_live_keys(monkeypatch, tmp_path):
    _patch_seeded_console_stores(monkeypatch, tmp_path)

    response = TestClient(api.app).post("/api/console/providers/openai/test")
    payload = response.json()

    assert response.status_code == 200
    assert payload["provider"]["provider"] == "openai"
    assert payload["test"]["live_call_performed"] is False
    assert payload["test"]["status"] == "not_configured"
    assert payload["cli_command"] == "blacklight health"
    assert payload["cli"]["health"] == "blacklight health"
    _assert_cli_command_parseable(payload["cli_command"])


def test_console_api_cli_affordances_include_prompt_compare_and_review_queue(monkeypatch, tmp_path):
    _patch_seeded_console_stores(monkeypatch, tmp_path)
    client = TestClient(api.app)

    prompts_response = client.get("/api/console/prompts/ticket_classifier")
    reviews_response = client.get("/api/console/reviews")
    dashboard_response = client.get("/api/dashboard")

    prompts_payload = prompts_response.json()
    reviews_payload = reviews_response.json()
    dashboard_payload = dashboard_response.json()

    assert prompts_response.status_code == 200
    assert reviews_response.status_code == 200
    assert dashboard_response.status_code == 200
    assert prompts_payload["cli_commands"]["compare"] == (
        "blacklight eval compare --baseline-version 1 --candidate-version 2"
    )
    assert reviews_payload["cli_command"].startswith("blacklight trace list")
    assert dashboard_payload["cli_commands"]["guided_demo"].startswith("blacklight demo")
    for command in [
        prompts_payload["cli_command"],
        prompts_payload["cli_commands"]["compare"],
        reviews_payload["cli_command"],
        dashboard_payload["cli_commands"]["guided_demo"],
        dashboard_payload["cli_commands"]["seed_demo_data"],
    ]:
        _assert_cli_command_parseable(command)


def test_console_settings_update_writes_user_env_without_exposing_secrets(monkeypatch, tmp_path):
    original_state = (
        api.settings,
        api.trace_store,
        api.idempotency_store,
        api.eval_store,
        api.review_store,
        api.classifier,
        api.classifier_startup_error,
    )
    user_env_path = tmp_path / "user.env"
    user_env_path.write_text("# console-managed settings\nPRIVATE_NOTE=keep\n", encoding="utf-8")
    monkeypatch.setenv("BLACKLIGHT_USER_ENV_PATH", str(user_env_path))
    for key in [
        "LLM_PROVIDER",
        "LLM_MODEL",
        "TRACE_DB_PATH",
        "OPENAI_API_KEY",
        "LLM_CUSTOM_PROVIDER",
    ]:
        monkeypatch.delenv(key, raising=False)

    try:
        response = TestClient(api.app).patch(
            "/api/console/settings",
            json={
                "settings": {
                    "LLM_PROVIDER": "openai",
                    "LLM_MODEL": "gpt-4o-mini",
                    "OPENAI_API_KEY": "sk-test-secret",
                    "TRACE_DB_PATH": str(tmp_path / "updated.sqlite3"),
                }
            },
        )
        payload = response.json()
        written = user_env_path.read_text(encoding="utf-8")
    finally:
        (
            api.settings,
            api.trace_store,
            api.idempotency_store,
            api.eval_store,
            api.review_store,
            api.classifier,
            api.classifier_startup_error,
        ) = original_state

    assert response.status_code == 200
    assert payload["updated_keys"] == [
        "LLM_MODEL",
        "LLM_PROVIDER",
        "OPENAI_API_KEY",
        "TRACE_DB_PATH",
    ]
    assert payload["settings"]["openai_configured"] is True
    assert payload["settings"]["user_env"]["managed_keys"]["OPENAI_API_KEY"]["value"] == "***"
    assert "sk-test-secret" not in str(payload)
    assert "PRIVATE_NOTE=keep" in written
    assert "OPENAI_API_KEY=sk-test-secret" in written
    assert payload["message"].endswith("The private .env file was not touched.")


def test_console_settings_update_rejects_unknown_user_env_keys(monkeypatch, tmp_path):
    original_state = (
        api.settings,
        api.trace_store,
        api.idempotency_store,
        api.eval_store,
        api.review_store,
        api.classifier,
        api.classifier_startup_error,
    )
    monkeypatch.setenv("BLACKLIGHT_USER_ENV_PATH", str(tmp_path / "user.env"))

    try:
        response = TestClient(api.app).patch(
            "/api/console/settings",
            json={"settings": {"SHELL": "powershell"}},
        )
    finally:
        (
            api.settings,
            api.trace_store,
            api.idempotency_store,
            api.eval_store,
            api.review_store,
            api.classifier,
            api.classifier_startup_error,
        ) = original_state

    assert response.status_code == 400
    assert "Unsupported user.env setting" in response.json()["detail"]


def test_console_settings_update_keeps_api_available_when_provider_extra_is_missing(
    monkeypatch,
    tmp_path,
):
    original_state = (
        api.settings,
        api.trace_store,
        api.idempotency_store,
        api.eval_store,
        api.review_store,
        api.classifier,
        api.classifier_startup_error,
    )
    monkeypatch.setenv("BLACKLIGHT_USER_ENV_PATH", str(tmp_path / "user.env"))
    monkeypatch.delenv("LLM_PROVIDER", raising=False)

    def missing_provider_extra(_settings):
        raise RuntimeError("Install the openai extra to use OpenAIProvider.")

    monkeypatch.setattr(api, "create_provider", missing_provider_extra)

    try:
        response = TestClient(api.app).patch(
            "/api/console/settings",
            json={
                "settings": {
                    "LLM_PROVIDER": "openai",
                    "OPENAI_API_KEY": "sk-test-secret",
                }
            },
        )
        payload = response.json()
        startup_error = api.classifier_startup_error
    finally:
        (
            api.settings,
            api.trace_store,
            api.idempotency_store,
            api.eval_store,
            api.review_store,
            api.classifier,
            api.classifier_startup_error,
        ) = original_state

    assert response.status_code == 200
    assert payload["settings"]["provider"] == "openai"
    assert startup_error is not None
    assert "openai extra" in str(startup_error)


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
    assert "blacklight health" in payload["error"]["next_step"]


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

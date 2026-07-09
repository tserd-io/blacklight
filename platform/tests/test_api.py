import importlib
import shlex
from dataclasses import replace

from fastapi.testclient import TestClient

from blacklight import api
from blacklight.cli import build_parser
from blacklight.demo_seed import seed_demo_data
from blacklight.errors import GuardrailValidationError
from blacklight.models import GuardrailOutcome, ProviderResponse, TraceRecord
from blacklight.observability.agent_runs import AgentRunStore
from blacklight.observability.evaluations import EvalMetricStore
from blacklight.observability.idempotency import IdempotencyStore
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


class StaticLocalModelStatus:
    def as_dict(self):
        return {
            "runtime": "ollama",
            "model": "llama3.1",
            "base_url": "http://localhost:11434",
            "provider_path": "blacklight.providers.ollama_provider:OllamaProvider",
            "configured": False,
            "selected": False,
            "installed": False,
            "available_models": [],
            "loading": False,
            "ready": False,
            "unavailable": True,
            "status": "unavailable",
            "status_message": "Local fallback model is not installed.",
            "start_command": "docker compose -f docker-compose.ollama.yml up -d",
            "install_command": "docker compose -f docker-compose.ollama.yml exec ollama ollama pull llama3.1",
            "fallback": {
                "type": "local_model",
                "configured": False,
                "provider": "ollama",
                "model": "llama3.1",
                "message": "Local model fallback is unavailable.",
                "hosted_provider": {
                    "configured": False,
                    "provider": None,
                    "secret_source": "private_environment",
                    "message": "Hosted provider credentials are not configured.",
                },
            },
            "tradeoffs": {
                "privacy_control": "Local inference can keep prompts on the user's machine.",
                "package_size": "First-run downloads keep the app smaller.",
                "hardware": "Local models depend on hardware.",
                "quality": "Smaller local models may need review.",
                "support": "A managed app should show model status.",
            },
        }


class InvalidJsonProvider:
    name = "invalid-json"

    def complete(self, request):
        return ProviderResponse(
            text="not-json",
            provider=self.name,
            model=request.model,
            input_tokens=1,
            output_tokens=1,
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
    agent_run_store = AgentRunStore(db_path)
    review_store = ReviewDecisionStore(db_path)
    monkeypatch.setattr(api, "trace_store", trace_store)
    monkeypatch.setattr(api, "eval_store", eval_store)
    monkeypatch.setattr(api, "agent_run_store", agent_run_store)
    monkeypatch.setattr(api, "review_store", review_store)
    monkeypatch.setattr(api, "local_model_status", lambda _settings: StaticLocalModelStatus())
    monkeypatch.setattr(api, "settings", replace(api.settings, trace_db_path=str(db_path)))
    return trace_store, eval_store, review_store


def _patch_agent_run_stores(monkeypatch, tmp_path):
    db_path = tmp_path / "agent-runs-api.sqlite3"
    trace_store = TraceStore(db_path)
    idempotency_store = IdempotencyStore(db_path)
    agent_run_store = AgentRunStore(db_path)
    monkeypatch.setattr(api, "trace_store", trace_store)
    monkeypatch.setattr(api, "idempotency_store", idempotency_store)
    monkeypatch.setattr(api, "agent_run_store", agent_run_store)
    monkeypatch.setattr(
        api,
        "settings",
        replace(
            api.settings,
            provider="mock",
            model="mock-ticket-classifier",
            trace_db_path=str(db_path),
        ),
    )
    return trace_store, agent_run_store


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


def test_agents_list_endpoint_returns_read_only_agent_summaries():
    response = TestClient(api.app).get("/api/agents")

    payload = response.json()

    assert response.status_code == 200
    assert payload["agents"][0]["agent_id"] == "ticket_classifier_agent"
    assert payload["agents"][0]["workflow_id"] == "ticket_classifier"
    assert payload["agents"][0]["output_schema"] == "TicketClassification"
    assert payload["agents"][0]["links"]["api"] == "/api/agents/ticket_classifier_agent"
    assert payload["cli_commands"]["list"] == "blacklight agents list"
    assert (
        payload["cli_commands"]["show_ticket_classifier"]
        == "blacklight agents show ticket_classifier_agent"
    )
    for command in payload["cli_commands"].values():
        _assert_cli_command_parseable(command)


def test_agent_profile_endpoint_returns_domain_range_and_trace_payload():
    response = TestClient(api.app).get("/api/agents/ticket_classifier_agent")

    payload = response.json()

    assert response.status_code == 200
    assert payload["agent_id"] == "ticket_classifier_agent"
    assert payload["domain"]["prompt_ids"] == ["ticket_classifier"]
    assert payload["governed_range"]["output_schema"] == "TicketClassification"
    assert "range" not in payload
    assert payload["related_workflow"]["workflow_id"] == "ticket_classifier"
    assert payload["prompts"][0]["prompt_id"] == "ticket_classifier"
    assert payload["prompts"][0]["versions"] == [1, 2]
    assert payload["eval_suite"]["run_api"] == "/api/console/evals/run"
    assert payload["trace_links"]["recent_traces_api"] == "/api/console/traces"
    assert payload["review_policy"]["review_queue_api"] == "/api/console/reviews"
    assert (
        "domain_boundary"
        in payload["domain_to_range_trace_contract"]["required_steps"]
    )
    assert payload["links"]["self"] == "/api/agents/ticket_classifier_agent"
    assert payload["cli_commands"]["show"] == (
        "blacklight agents show ticket_classifier_agent"
    )
    for command in payload["cli_commands"].values():
        _assert_cli_command_parseable(command)


def test_agent_profile_endpoint_returns_known_error_for_missing_agent():
    response = TestClient(api.app).get("/api/agents/missing_agent")

    payload = response.json()

    assert response.status_code == 404
    assert payload["detail"]["category"] == "agent_not_found"
    assert payload["detail"]["message"] == "Agent not found: missing_agent"
    assert payload["detail"]["next_step"] == (
        "Run `blacklight agents list` and retry with a listed agent_id."
    )


def test_agent_run_api_runs_ticket_classifier_and_persists_envelope(monkeypatch, tmp_path):
    trace_store, agent_run_store = _patch_agent_run_stores(monkeypatch, tmp_path)

    response = TestClient(api.app).post(
        "/api/agents/ticket_classifier_agent/runs",
        json={
            "subject": "Refund request",
            "body": "Customer asks for a refund after duplicate billing.",
            "session_id": "api-agent-session",
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["agent_run"]["agent_id"] == "ticket_classifier_agent"
    assert payload["agent_run"]["session_id"] == "api-agent-session"
    assert payload["agent_run"]["run_status"] == "completed"
    assert payload["run_id"].startswith("agent-run-")
    assert payload["trace_id"]
    assert payload["output_summary"]["category"] == "billing"
    assert payload["validation"]["guardrail_outcome"] == "accepted"
    assert payload["links"]["self"] == f"/api/agent-runs/{payload['run_id']}"
    assert "blacklight agents run ticket_classifier_agent" in payload["cli_command"]
    assert "blacklight agents runs show" in payload["cli"]["show"]
    _assert_cli_command_parseable(payload["cli_command"])
    _assert_cli_command_parseable(payload["cli"]["show"])

    traces = trace_store.list_by_agent_run_id(payload["run_id"])
    envelope = agent_run_store.get(payload["run_id"])
    assert len(traces) == 1
    assert traces[0]["request_id"] == payload["trace_id"]
    assert traces[0]["session_id"] == "api-agent-session"
    assert traces[0]["agent_run_id"] == payload["run_id"]
    assert envelope is not None
    assert envelope["trace_request_id"] == payload["trace_id"]
    assert envelope["context_bundle"]["raw_inputs_persisted"] is False

    lookup_response = TestClient(api.app).get(f"/api/agent-runs/{payload['run_id']}")
    assert lookup_response.status_code == 200
    assert lookup_response.json()["agent_run"]["agent_run_id"] == payload["run_id"]


def test_agent_run_api_returns_unknown_agent_error():
    response = TestClient(api.app).post(
        "/api/agents/missing_agent/runs",
        json={"subject": "Refund request", "body": "Duplicate billing."},
    )

    payload = response.json()

    assert response.status_code == 404
    assert payload["detail"]["category"] == "agent_not_found"


def test_agent_run_api_rejects_invalid_input():
    response = TestClient(api.app).post(
        "/api/agents/ticket_classifier_agent/runs",
        json={"subject": "Refund request"},
    )

    assert response.status_code == 422


def test_agent_run_api_returns_review_routed_output(monkeypatch, tmp_path):
    _trace_store, agent_run_store = _patch_agent_run_stores(monkeypatch, tmp_path)

    response = TestClient(api.app).post(
        "/api/agents/ticket_classifier_agent/runs",
        json={
            "subject": "Possible fraud",
            "body": "Customer reports possible fraud on a billing account.",
            "session_id": "api-agent-review",
        },
    )
    payload = response.json()
    envelope = agent_run_store.get(payload["run_id"])

    assert response.status_code == 200
    assert payload["agent_run"]["run_status"] == "completed"
    assert payload["validation"]["guardrail_outcome"] == "needs_review"
    assert payload["validation"]["review_state"] == "needs_review"
    assert payload["validation"]["review_required"] is True
    assert payload["validation"]["review_reason"].startswith("Guardrails routed")
    assert payload["review"]["routing_decision"] == "block_downstream_touch"
    assert payload["output_summary"]["needs_review"] is True
    assert envelope["review"]["state"] == "needs_review"
    assert envelope["review"]["reason"].startswith("Guardrails routed")
    assert envelope["review"]["touch_decision"] == "block_downstream_touch"


def test_agent_run_api_persists_failed_validation_payload(monkeypatch, tmp_path):
    trace_store, agent_run_store = _patch_agent_run_stores(monkeypatch, tmp_path)
    monkeypatch.setattr(api, "create_provider", lambda _settings: InvalidJsonProvider())

    response = TestClient(api.app).post(
        "/api/agents/ticket_classifier_agent/runs",
        json={
            "subject": "Refund request",
            "body": "Customer asks for a refund after duplicate billing.",
            "session_id": "api-agent-validation-failure",
        },
    )
    payload = response.json()

    assert response.status_code == 422
    assert payload["agent_run"]["run_status"] == "failed"
    assert payload["validation"]["guardrail_outcome"] == "rejected"
    assert payload["validation"]["review_state"] == "rejected"
    assert payload["validation"]["review_reason"].startswith("Guardrails rejected")
    assert payload["validation"]["errors"]
    assert payload["output_summary"] is None
    assert payload["error"]["category"] == "validation_error"
    assert payload["links"]["trace"] == f"/api/console/traces/{payload['trace_id']}"
    assert trace_store.list_by_agent_run_id(payload["run_id"])
    envelope = agent_run_store.get(payload["run_id"])
    assert envelope is not None
    assert envelope["run_status"] == "failed"
    assert envelope["guardrail"]["outcome"] == "rejected"
    assert envelope["review"]["reason"].startswith("Guardrails rejected")


def test_console_dashboard_exposes_demo_and_recent_inspection_links(monkeypatch, tmp_path):
    _patch_seeded_console_stores(monkeypatch, tmp_path)

    response = TestClient(api.app).get("/console")

    assert response.status_code == 200
    assert "Blacklight Studio" in response.text
    assert "Run Agent" in response.text
    assert "/console/agents/ticket_classifier_agent/run" in response.text
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
        "/console/first-run": "First Run",
        "/console/workflows": "blacklight agents demo",
        "/console/agents": "blacklight agents list",
        "/console/runs": "blacklight session show",
        "/console/traces": "blacklight trace list",
        "/console/evals": "blacklight eval list",
        "/console/prompts": "blacklight prompts list",
        "/console/providers": "blacklight health",
        "/console/local-model": "blacklight local-model status",
        "/console/review": "Review Queue",
        "/console/settings": "blacklight health",
        "/console/docs": "Docs And Recipes",
    }

    for path, expected_text in expected.items():
        response = client.get(path)
        assert response.status_code == 200
        assert "Blacklight Studio" in response.text
        assert expected_text in response.text


def test_console_agents_list_links_to_read_only_profile():
    response = TestClient(api.app).get("/console/agents")

    assert response.status_code == 200
    assert "Agents" in response.text
    assert "Ticket Classifier Agent" in response.text
    assert "/console/agents/ticket_classifier_agent" in response.text
    assert "blacklight agents list" in response.text
    assert "blacklight agents show ticket_classifier_agent" in response.text


def test_console_agent_profile_shows_domain_range_trace_links_and_cli():
    response = TestClient(api.app).get("/console/agents/ticket_classifier_agent")

    assert response.status_code == 200
    assert "Ticket Classifier Agent" in response.text
    assert "Domain" in response.text
    assert "Range" in response.text
    assert "Domain-To-Range Trace" in response.text
    assert "/console/prompts" in response.text
    assert "/console/evals" in response.text
    assert "/console/traces" in response.text
    assert "/console/review" in response.text
    assert "/console/workflows" in response.text
    assert "/console/agents/ticket_classifier_agent/run" in response.text
    assert "Seeded Run Inputs" in response.text
    assert "Copy" in response.text
    assert "CLI Equivalent" in response.text
    assert "blacklight agents show ticket_classifier_agent" in response.text
    assert "blacklight agents show ticket_classifier_agent --json" in response.text
    assert "blacklight agents demo ticket_classifier_agent" in response.text
    assert "blacklight prompts show ticket_classifier" in response.text


def test_console_run_demo_links_result_to_trace_and_session(monkeypatch, tmp_path):
    trace_store, _eval_store, _review_store = _patch_seeded_console_stores(monkeypatch, tmp_path)

    response = TestClient(api.app).post("/console/run-demo")
    traces = trace_store.list_by_session_id("console-agent-demo", limit=10)

    assert response.status_code == 200
    assert "Agent Run Result" in response.text
    assert "billing" in response.text
    assert "/sessions/console-agent-demo" in response.text
    assert "blacklight trace show" in response.text
    assert len(traces) == 1
    assert traces[0]["session_id"] == "console-agent-demo"
    assert traces[0]["agent_run_id"]


def test_console_agent_run_journey_shows_clickable_trace_and_copyable_cli(monkeypatch, tmp_path):
    trace_store, _eval_store, _review_store = _patch_seeded_console_stores(monkeypatch, tmp_path)

    response = TestClient(api.app).post("/console/agents/ticket_classifier_agent/run")
    traces = trace_store.list_by_session_id("console-agent-demo", limit=10)
    trace = traces[-1]

    assert response.status_code == 200
    assert "Agent Run Result" in response.text
    assert "Seeded Inputs" in response.text
    assert "Output Summary" in response.text
    assert "Trace Path" in response.text
    assert "Domain Inputs" in response.text
    assert "Guardrails" in response.text
    assert "Review/Eval" in response.text
    assert "accepted" in response.text
    assert f"/api/console/traces/{trace['request_id']}" in response.text
    assert "copy-command" in response.text
    assert "navigator.clipboard.writeText" in response.text
    assert 'onclick="this.select()"' in response.text
    assert 'onfocus="this.select()"' in response.text
    assert "blacklight agents demo ticket_classifier_agent" in response.text


def test_console_agent_run_uses_mock_demo_even_when_live_provider_is_unconfigured(
    monkeypatch,
    tmp_path,
):
    trace_store, _eval_store, _review_store = _patch_seeded_console_stores(monkeypatch, tmp_path)
    trace_db_path = api.settings.trace_db_path
    monkeypatch.setattr(
        api,
        "settings",
        replace(
            api.settings,
            provider="openai",
            openai_api_key=None,
            trace_db_path=trace_db_path,
        ),
    )

    response = TestClient(api.app).post("/console/agents/ticket_classifier_agent/run")
    traces = trace_store.list_by_session_id("console-agent-demo", limit=10)

    assert response.status_code == 200
    assert "Agent Run Result" in response.text
    assert "billing" in response.text
    assert traces[-1]["provider"] == "mock"
    assert traces[-1]["model"] == "mock-ticket-classifier"


def test_console_agent_run_error_state_explains_known_error():
    response = TestClient(api.app).post("/console/agents/missing_agent/run")

    assert response.status_code == 404
    assert "Agent Run Could Not Start" in response.text
    assert "agent_not_found" in response.text
    assert "Agent not found: missing_agent" in response.text
    assert "blacklight agents list" in response.text
    assert "blacklight agents demo missing_agent" in response.text


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
    assert payload["local_model"]["status"] == "unavailable"
    assert payload["local_model"]["cli_command"] == "blacklight local-model status"
    assert payload["first_run"]["modes"][0]["mode"] == "demo"
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


def test_console_api_agent_run_envelope_lookup_links_trace(monkeypatch, tmp_path):
    db_path = tmp_path / "agent-runs.sqlite3"
    trace_store = TraceStore(db_path)
    agent_run_store = AgentRunStore(db_path)
    trace_store.insert(
        TraceRecord(
            request_id="trace-1",
            session_id="agent-session",
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
    envelope = {
        "agent_run_id": "agent-run-1",
        "agent_id": "ticket_classifier_agent",
        "agent_version": 1,
        "workflow_id": "ticket_classifier",
        "run_status": "completed",
        "session_id": "agent-session",
        "trace_request_id": "trace-1",
        "trace_id": "trace-1",
        "domain_snapshot": {"prompt_ids": ["ticket_classifier"]},
        "context_bundle": {"raw_inputs_persisted": False},
        "provider_call": {"provider": "mock", "model": "mock-ticket-classifier"},
        "validation": {"passed": True, "errors": []},
        "guardrail": {
            "outcome": "accepted",
            "reason": "Guardrails accepted this output for read-only range use.",
            "error_category": None,
        },
        "range_output": {"output": {"category": "billing"}},
        "review": {
            "state": "accepted",
            "required": False,
            "reason": "Guardrails accepted this output for read-only range use.",
            "routing_decision": "allow_read_only_output",
        },
        "eval_evidence": {"eval_run_id": None, "linked": False},
    }
    agent_run_store.insert(envelope)
    monkeypatch.setattr(api, "trace_store", trace_store)
    monkeypatch.setattr(api, "agent_run_store", agent_run_store)
    monkeypatch.setattr(api, "settings", replace(api.settings, trace_db_path=str(db_path)))
    client = TestClient(api.app)

    list_response = client.get("/api/console/agent-runs")
    show_response = client.get("/api/console/agent-runs/agent-run-1")
    trace_response = client.get("/api/console/traces/trace-1")

    assert list_response.status_code == 200
    assert list_response.json()["agent_runs"][0]["agent_run_id"] == "agent-run-1"
    assert list_response.json()["agent_runs"][0]["review"]["reason"].startswith("Guardrails accepted")
    assert (
        list_response.json()["agent_runs"][0]["review"]["routing_decision"]
        == "allow_read_only_output"
    )
    assert show_response.status_code == 200
    assert show_response.json()["agent_run"]["agent_run_id"] == "agent-run-1"
    assert show_response.json()["agent_run"]["context_bundle"]["raw_inputs_persisted"] is False
    assert "blacklight agents runs show agent-run-1" in show_response.json()["cli_command"]
    assert trace_response.status_code == 200
    assert trace_response.json()["trace"]["links"]["agent_run_api"] == (
        "/api/console/agent-runs/agent-run-1"
    )
    assert "blacklight agents runs show agent-run-1" in trace_response.json()["trace"]["cli"]["agent_run"]
    assert trace_response.json()["trace"]["domain_to_range"]["agent_run"]["agent_run_id"] == (
        "agent-run-1"
    )
    assert trace_response.json()["trace"]["domain_to_range"]["domain"]["prompt_ids"] == [
        "ticket_classifier"
    ]
    assert trace_response.json()["trace"]["domain_to_range"]["context"]["raw_inputs_persisted"] is False
    assert trace_response.json()["trace"]["domain_to_range"]["provider"]["provider"] == "mock"
    assert trace_response.json()["trace"]["domain_to_range"]["validation"]["passed"] is True
    assert trace_response.json()["trace"]["domain_to_range"]["guardrails"]["outcome"] == "accepted"
    assert trace_response.json()["trace"]["domain_to_range"]["review_reason"].startswith(
        "Guardrails accepted"
    )
    assert trace_response.json()["trace"]["domain_to_range"]["range"]["output"]["category"] == "billing"
    assert trace_response.json()["trace"]["domain_to_range"]["review"]["state"] == "accepted"
    assert trace_response.json()["trace"]["domain_to_range"]["eval_evidence"]["linked"] is False


def test_console_api_surfaces_return_state_and_cli(monkeypatch, tmp_path):
    _patch_seeded_console_stores(monkeypatch, tmp_path)
    client = TestClient(api.app)
    endpoints = [
        ("/api/console/workflows", "workflows"),
        ("/api/console/first-run", "modes"),
        ("/api/console/workflows/ticket_classifier", "workflow"),
        ("/api/console/runs", "runs"),
        ("/api/console/runs/seed-demo", "traces"),
        ("/api/console/traces", "traces"),
        ("/api/console/traces/seed-demo:billing-success", "trace"),
        ("/api/console/agent-runs", "agent_runs"),
        ("/api/console/evals", "eval_runs"),
        ("/api/console/evals/seed-demo-eval", "eval_run"),
        ("/api/console/prompts", "prompts"),
        ("/api/console/prompts/ticket_classifier", "prompt"),
        ("/api/console/providers", "providers"),
        ("/api/console/local-model", "runtime"),
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


def test_console_settings_update_writes_user_env_without_editing_private_keys(
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
    user_env_path = tmp_path / "user.env"
    user_env_path.write_text("# console-managed settings\nPRIVATE_NOTE=keep\n", encoding="utf-8")
    monkeypatch.setenv("BLACKLIGHT_USER_ENV_PATH", str(user_env_path))
    for key in [
        "LLM_PROVIDER",
        "LLM_MODEL",
        "TRACE_DB_PATH",
        "LLM_CUSTOM_PROVIDER",
    ]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-private-process-secret")

    try:
        response = TestClient(api.app).patch(
            "/api/console/settings",
            json={
                "settings": {
                    "LLM_PROVIDER": "openai",
                    "LLM_MODEL": "gpt-4o-mini",
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
        "TRACE_DB_PATH",
    ]
    assert payload["settings"]["openai_configured"] is True
    assert "OPENAI_API_KEY" not in payload["settings"]["user_env"]["managed_keys"]
    assert "sk-private-process-secret" not in str(payload)
    assert "PRIVATE_NOTE=keep" in written
    assert "OPENAI_API_KEY" not in written
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
    monkeypatch.setenv("OPENAI_API_KEY", "sk-private-process-secret")

    def missing_provider_extra(_settings):
        raise RuntimeError("Install the openai extra to use OpenAIProvider.")

    monkeypatch.setattr(api, "create_provider", missing_provider_extra)

    try:
        response = TestClient(api.app).patch(
            "/api/console/settings",
            json={
                "settings": {
                    "LLM_PROVIDER": "openai",
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


def test_console_first_run_payload_explains_modes_without_jargon(monkeypatch, tmp_path):
    _patch_seeded_console_stores(monkeypatch, tmp_path)

    response = TestClient(api.app).get("/api/console/first-run")
    payload = response.json()

    assert response.status_code == 200
    assert payload["title"] == "First-run provider setup"
    assert {mode["mode"] for mode in payload["modes"]} == {
        "demo",
        "hosted_provider",
        "local_model",
    }
    hosted = next(mode for mode in payload["modes"] if mode["mode"] == "hosted_provider")
    local = next(mode for mode in payload["modes"] if mode["mode"] == "local_model")

    assert hosted["plain_language"]["cost"] == "Usage may create token charges."
    assert hosted["readiness_label"] == "Needs private provider key"
    assert "private environment" in hosted["recovery_steps"][0]
    assert local["settings"]["LLM_CUSTOM_PROVIDER"].endswith("OllamaProvider")
    assert "Check Local Model status" in local["recovery_steps"][2]


def test_console_first_run_save_writes_local_model_settings_without_secrets(
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
    user_env_path = tmp_path / "user.env"
    monkeypatch.setenv("BLACKLIGHT_USER_ENV_PATH", str(user_env_path))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(api, "local_model_status", lambda _settings: StaticLocalModelStatus())

    try:
        response = TestClient(api.app).post(
            "/api/console/first-run",
            json={
                "mode": "local_model",
                "model": "llama3.1",
                "ollama_base_url": "http://localhost:11434",
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
    assert payload["mode"] == "local_model"
    assert payload["updated_keys"] == [
        "LLM_CUSTOM_PROVIDER",
        "LLM_MODEL",
        "LLM_PROVIDER",
        "OLLAMA_BASE_URL",
    ]
    assert "LLM_PROVIDER=custom" in written
    assert "LLM_CUSTOM_PROVIDER=blacklight.providers.ollama_provider:OllamaProvider" in written
    assert "OPENAI_API_KEY" not in written


def test_console_first_run_save_rejects_unknown_mode(monkeypatch, tmp_path):
    monkeypatch.setenv("BLACKLIGHT_USER_ENV_PATH", str(tmp_path / "user.env"))

    response = TestClient(api.app).post(
        "/api/console/first-run",
        json={"mode": "mystery"},
    )

    assert response.status_code == 400
    assert "Choose demo, hosted_provider, or local_model" in response.json()["detail"]


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

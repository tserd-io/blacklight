import json

import pytest

from blacklight.cli import main
from blacklight.models import GuardrailOutcome, ProviderRequest, ProviderResponse, TraceRecord
from blacklight.observability.agent_runs import AgentRunStore
from blacklight.observability.evaluations import EvalMetricStore
from blacklight.observability.storage import TraceStore


def test_classify_command_prints_ticket_json(capsys, tmp_path):
    exit_code = main(
        [
            "classify",
            "--subject",
            "Refund",
            "--body",
            "Duplicate charge",
            "--trace-db-path",
            str(tmp_path / "traces.sqlite3"),
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["category"] == "billing"
    assert payload["severity"] == "medium"


def test_demo_command_runs_mock_workflow_and_prints_next_steps(capsys, tmp_path):
    trace_db_path = tmp_path / "traces.sqlite3"

    exit_code = main(["demo", "--verbose", "--trace-db-path", str(trace_db_path)])
    payload = json.loads(capsys.readouterr().out)
    traces = TraceStore(trace_db_path).list_by_session_id("demo")

    assert exit_code == 0
    assert payload["demo"] == "ticket_classifier"
    assert payload["message"] == "Mock-mode demo completed without live provider credentials."
    assert payload["sample_input"]["subject"] == "Refund request"
    assert payload["result"]["category"] == "billing"
    assert payload["result"]["severity"] == "medium"
    assert payload["trace"]["request_id"] == traces[0]["request_id"]
    assert payload["trace"]["trace_db_path"] == str(trace_db_path)
    assert "blacklight trace show" in payload["trace"]["inspect_command"]
    assert "blacklight session show demo" in payload["trace"]["session_command"]
    assert "blacklight classify" in payload["next_commands"]["equivalent_workflow_command"]
    assert "--subject" in payload["next_commands"]["equivalent_workflow_command"]
    assert "blacklight eval run" in payload["next_commands"]["eval_command"]
    assert payload["runtime"]["provider"] == "mock"
    assert payload["runtime"]["live_credentials_required"] is False
    assert payload["trace"]["record"]["provider"] == "mock"


def test_demo_command_ignores_live_provider_environment(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    trace_db_path = tmp_path / "traces.sqlite3"

    exit_code = main(["demo", "--trace-db-path", str(trace_db_path)])
    payload = json.loads(capsys.readouterr().out)
    traces = TraceStore(trace_db_path).list_by_session_id("demo")

    assert exit_code == 0
    assert payload["result"]["category"] == "billing"
    assert traces[0]["provider"] == "mock"
    assert traces[0]["model"] == "mock-ticket-classifier"


def test_seed_demo_data_command_populates_mock_surfaces(capsys, tmp_path):
    trace_db_path = tmp_path / "seed.sqlite3"

    exit_code = main(["seed", "demo-data", "--trace-db-path", str(trace_db_path)])
    payload = json.loads(capsys.readouterr().out)
    traces = TraceStore(trace_db_path).list_by_session_id("seed-demo", limit=20)
    eval_run = EvalMetricStore(trace_db_path).get_run("seed-demo-eval")

    assert exit_code == 0
    assert payload["seed"] == "mock_mode_demo_data"
    assert payload["runs"][1]["guardrail_outcome"] == "needs_review"
    assert payload["eval_run"]["case_count"] == 3
    assert len(traces) == 5
    assert eval_run is not None
    assert eval_run["session_id"] == "seed-demo"


def test_eval_command_prints_summary(capsys, tmp_path):
    trace_db_path = tmp_path / "traces.sqlite3"
    exit_code = main(
        [
            "eval",
            "--session-id",
            "eval-session",
            "--trace-db-path",
            str(trace_db_path),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    runs = EvalMetricStore(trace_db_path).list_runs()

    assert exit_code == 0
    assert payload["session_id"] == "eval-session"
    assert payload["summary"]["accuracy"] == 1.0
    assert payload["summary"]["total_tokens"] > 0
    assert payload["cases"]
    assert runs[0]["eval_run_id"] == payload["eval_run_id"]
    assert runs[0]["session_id"] == "eval-session"


def test_eval_run_subcommand_prints_summary(capsys, tmp_path):
    trace_db_path = tmp_path / "traces.sqlite3"
    exit_code = main(
        [
            "eval",
            "run",
            "--session-id",
            "eval-session",
            "--trace-db-path",
            str(trace_db_path),
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["session_id"] == "eval-session"
    assert payload["summary"]["accuracy"] == 1.0


def test_eval_run_subcommand_accepts_prompt_version(capsys, tmp_path):
    trace_db_path = tmp_path / "traces.sqlite3"
    exit_code = main(
        [
            "eval",
            "run",
            "--prompt-version",
            "2",
            "--trace-db-path",
            str(trace_db_path),
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["prompt_version"] == 2
    assert payload["summary"]["accuracy"] == 1.0


def test_eval_compare_command_prints_prompt_version_report(capsys):
    exit_code = main(
        [
            "eval",
            "compare",
            "--baseline-version",
            "1",
            "--candidate-version",
            "2",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["comparison_group"] == "support_ticket_classification"
    assert payload["baseline"]["prompt_version"] == 1
    assert payload["candidate"]["prompt_version"] == 2
    assert payload["summary_deltas"]["accuracy"]["delta"] == 0.0
    assert payload["case_changes"]


def test_eval_history_commands_read_persisted_runs(capsys, tmp_path):
    trace_db_path = tmp_path / "traces.sqlite3"
    main(
        [
            "eval",
            "run",
            "--session-id",
            "eval-session",
            "--trace-db-path",
            str(trace_db_path),
        ]
    )
    run_payload = json.loads(capsys.readouterr().out)

    list_exit_code = main(["eval", "list", "--trace-db-path", str(trace_db_path)])
    list_payload = json.loads(capsys.readouterr().out)
    show_exit_code = main(
        [
            "eval",
            "show",
            run_payload["eval_run_id"],
            "--trace-db-path",
            str(trace_db_path),
        ]
    )
    show_payload = json.loads(capsys.readouterr().out)

    assert list_exit_code == 0
    assert show_exit_code == 0
    assert list_payload["eval_runs"][0]["eval_run_id"] == run_payload["eval_run_id"]
    assert show_payload["eval_run"]["eval_run_id"] == run_payload["eval_run_id"]
    assert show_payload["eval_run"]["cases"]
    assert show_payload["eval_run"]["cases"][0]["trace_request_id"]
    assert show_payload["traces"][0]["eval_run_id"] == run_payload["eval_run_id"]


def test_metrics_command_reads_trace_db(capsys, tmp_path):
    trace_db_path = tmp_path / "traces.sqlite3"
    main(
        [
            "classify",
            "--subject",
            "Refund",
            "--body",
            "Duplicate charge",
            "--trace-db-path",
            str(trace_db_path),
        ]
    )
    capsys.readouterr()

    exit_code = main(["metrics", "--trace-db-path", str(trace_db_path)])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["request_count"] == 1
    assert payload["total_estimated_cost_usd"] == 0
    assert payload["failure_rate"] == 0.0
    assert payload["by_provider"][0]["provider"] == "mock"
    assert payload["by_model"][0]["model"] == "mock-ticket-classifier"
    assert payload["by_guardrail_outcome"][0]["guardrail_outcome"] == "accepted"


def test_health_command_prints_runtime_config(capsys):
    exit_code = main(["health"])

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["provider"] == "mock"
    assert payload["model"] == "mock-ticket-classifier"
    assert payload["openai_configured"] is False
    assert payload["custom_provider_configured"] is False
    assert payload["ollama_base_url"] == "http://localhost:11434"
    assert payload["provider_timeout_seconds"] == 30.0
    assert payload["provider_max_retries"] == 2
    assert payload["provider_rate_limit_requests"] == 3
    assert payload["provider_rate_limit_window_seconds"] == 10.0


def test_providers_list_command_prints_mock_safe_configuration(capsys):
    exit_code = main(["providers", "list"])

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["active_provider"] == "mock"
    providers = {provider["name"]: provider for provider in payload["providers"]}
    assert providers["mock"]["configured"] is True
    assert providers["mock"]["selected"] is True
    assert providers["mock"]["requires_secret"] is False
    assert providers["openai"]["configured"] is False
    assert providers["openai"]["requires_secret"] is True
    assert providers["custom"]["configured"] is False


def test_providers_status_command_prints_runtime_readiness(capsys, monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "https://example.com")

    exit_code = main(["providers", "status"])

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["runtime"]["provider"] == "mock"
    assert payload["providers"]["mock"]["ready"] is True
    assert payload["providers"]["mock"]["selected"] is True
    assert payload["providers"]["openai"]["ready"] is False
    assert payload["providers"]["custom"]["ready"] is False
    assert payload["local_model"]["runtime"] == "ollama"
    assert payload["local_model"]["status"] == "unavailable"
    assert payload["local_model"]["ready"] is False


def test_local_model_status_command_prints_readiness(capsys, monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "https://example.com")

    exit_code = main(["local-model", "status"])

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["runtime"] == "ollama"
    assert payload["status"] == "unavailable"
    assert payload["ready"] is False
    assert payload["fallback"]["configured"] is False


def test_agents_list_command_prints_human_readable_summary(capsys):
    exit_code = main(["agents", "list"])

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Managed Agents" in output
    assert "ticket_classifier_agent" in output
    assert "workflow: ticket_classifier" in output
    assert "blacklight agents show ticket_classifier_agent" in output


def test_agents_list_json_command_prints_stable_payload(capsys):
    exit_code = main(["agents", "list", "--json"])

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["agents"][0]["agent_id"] == "ticket_classifier_agent"
    assert payload["agents"][0]["workflow_id"] == "ticket_classifier"
    assert payload["agents"][0]["output_schema"] == "TicketClassification"
    assert payload["agents"][0]["cli_command"] == "blacklight agents show ticket_classifier_agent"
    assert payload["cli_commands"]["list"] == "blacklight agents list"


def test_agents_show_command_prints_domain_range_and_trace_contract(capsys):
    exit_code = main(["agents", "show", "ticket_classifier_agent"])

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Ticket Classifier Agent (ticket_classifier_agent)" in output
    assert "Domain" in output
    assert "Retrieval surface:" in output
    assert "Governed Range" in output
    assert "Output schema: TicketClassification" in output
    assert "Domain-To-Range Traceability" in output
    assert "guardrail_decision" in output
    assert "blacklight agents show ticket_classifier_agent --json" in output


def test_agents_show_json_command_prints_stable_payload(capsys):
    exit_code = main(["agents", "show", "ticket_classifier_agent", "--json"])

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["agent_id"] == "ticket_classifier_agent"
    assert payload["workflow_id"] == "ticket_classifier"
    assert payload["domain"]["prompt_ids"] == ["ticket_classifier"]
    assert payload["domain"]["prompt_versions"]["ticket_classifier"] == [1, 2]
    assert payload["governed_range"]["output_schema"] == "TicketClassification"
    assert "guardrail_decision" in payload["trace_contract"]["required_steps"]
    assert payload["cli_commands"]["show"] == "blacklight agents show ticket_classifier_agent"
    assert payload["cli_commands"]["show_json"] == (
        "blacklight agents show ticket_classifier_agent --json"
    )


def test_agents_show_missing_agent_prints_known_error(capsys):
    exit_code = main(["agents", "show", "missing_agent"])

    captured = capsys.readouterr()
    payload = json.loads(captured.err)

    assert exit_code == 1
    assert captured.out == ""
    assert payload["error"]["category"] == "agent_not_found"
    assert payload["error"]["message"] == "Agent not found: missing_agent"
    assert "blacklight agents list" in payload["error"]["next_step"]


def test_agents_run_json_command_returns_run_and_trace_ids(capsys, tmp_path):
    trace_db_path = tmp_path / "agent-run.sqlite3"

    exit_code = main(
        [
            "agents",
            "run",
            "ticket_classifier_agent",
            "--subject",
            "Refund request",
            "--body",
            "Customer asks for a refund after duplicate billing.",
            "--trace-db-path",
            str(trace_db_path),
            "--session-id",
            "agent-run-session",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    run_id = payload["agent_run"]["run_id"]
    trace_store = TraceStore(trace_db_path)
    traces = trace_store.list_by_session_id("agent-run-session")
    agent_run_traces = trace_store.list_by_agent_run_id(run_id)
    envelope = AgentRunStore(trace_db_path).get(run_id)

    assert exit_code == 0
    assert payload["agent_run"]["agent_id"] == "ticket_classifier_agent"
    assert payload["agent_run"]["workflow_id"] == "ticket_classifier"
    assert payload["agent_run"]["run_id"].startswith("agent-run-")
    assert payload["agent_run"]["run_status"] == "completed"
    assert payload["agent_run"]["requested_session_id"] == "agent-run-session"
    assert payload["agent_run"]["session_id"] == "agent-run-session"
    assert payload["trace"]["trace_id"] == traces[0]["request_id"]
    assert payload["trace"]["session_id"] == "agent-run-session"
    assert payload["trace"]["agent_run_id"] == run_id
    assert agent_run_traces[0]["request_id"] == payload["trace"]["trace_id"]
    assert "preserves the requested session" in payload["trace"]["session_linkage"]
    assert payload["validation"]["passed"] is True
    assert payload["validation"]["guardrail_outcome"] == "accepted"
    assert payload["validation"]["review_required"] is False
    assert payload["output_summary"]["category"] == "billing"
    assert payload["output"]["category"] == "billing"
    assert payload["trace_envelope"]["agent_run_id"] == run_id
    assert envelope is not None
    assert envelope["agent_run_id"] == run_id
    assert envelope["session_id"] == "agent-run-session"
    assert envelope["trace_request_id"] == payload["trace"]["trace_id"]
    assert envelope["domain_snapshot"]["prompt_ids"] == ["ticket_classifier"]
    assert envelope["context_bundle"]["raw_inputs_persisted"] is False
    assert envelope["context_bundle"]["prompt_text_persisted"] is False
    assert envelope["context_bundle"]["inputs"]["subject"]["length"] == len("Refund request")
    assert "Refund request" not in json.dumps(envelope)
    assert "Customer asks for a refund after duplicate billing." not in json.dumps(envelope)
    assert envelope["provider_call"]["prompt_text_persisted"] is False
    assert envelope["validation"]["passed"] is True
    assert envelope["guardrail"]["outcome"] == "accepted"
    assert envelope["range_output"]["output"]["category"] == "billing"
    assert envelope["review"]["state"] == "accepted"

    list_exit_code = main(
        ["agents", "runs", "list", "--trace-db-path", str(trace_db_path)]
    )
    list_payload = json.loads(capsys.readouterr().out)
    show_exit_code = main(
        ["agents", "runs", "show", run_id, "--trace-db-path", str(trace_db_path)]
    )
    show_payload = json.loads(capsys.readouterr().out)
    trace_show_exit_code = main(
        ["traces", "show", payload["trace"]["trace_id"], "--trace-db-path", str(trace_db_path), "--json"]
    )
    trace_show_payload = json.loads(capsys.readouterr().out)

    assert list_exit_code == 0
    assert list_payload["agent_runs"][0]["agent_run_id"] == run_id
    assert show_exit_code == 0
    assert show_payload["agent_run"] == envelope
    assert trace_show_exit_code == 0
    assert trace_show_payload["trace"]["domain_to_range"]["agent_run"]["agent_run_id"] == run_id
    assert trace_show_payload["trace"]["domain_to_range"]["domain"]["prompt_ids"] == [
        "ticket_classifier"
    ]
    assert trace_show_payload["trace"]["domain_to_range"]["context"]["raw_inputs_persisted"] is False
    assert trace_show_payload["trace"]["domain_to_range"]["provider"]["provider"] == "mock"
    assert trace_show_payload["trace"]["domain_to_range"]["validation"]["passed"] is True
    assert trace_show_payload["trace"]["domain_to_range"]["guardrails"]["outcome"] == "accepted"
    assert trace_show_payload["trace"]["domain_to_range"]["range"]["output"]["category"] == "billing"
    assert trace_show_payload["trace"]["domain_to_range"]["review"]["state"] == "accepted"
    assert trace_show_payload["trace"]["domain_to_range"]["eval_evidence"]["linked"] is False


def test_agents_run_verbose_command_prints_traceable_summary(capsys, tmp_path):
    trace_db_path = tmp_path / "agent-run.sqlite3"

    exit_code = main(
        [
            "agents",
            "run",
            "ticket_classifier_agent",
            "--subject",
            "Refund request",
            "--body",
            "Customer asks for a refund after duplicate billing.",
            "--trace-db-path",
            str(trace_db_path),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Managed Agent Run" in output
    assert "Agent: ticket_classifier_agent v1" in output
    assert "Run ID: agent-run-" in output
    assert "Trace ID:" in output
    assert "guardrail outcome: accepted" in output
    assert "Domain-To-Range Evidence" in output
    assert "blacklight trace show" in output


def test_agents_run_json_command_reports_review_validation_path(capsys, tmp_path):
    trace_db_path = tmp_path / "agent-run-review.sqlite3"

    exit_code = main(
        [
            "agents",
            "run",
            "ticket_classifier_agent",
            "--subject",
            "Account contact update",
            "--body",
            "Synthetic customer asks to update contact email to sample@example.com.",
            "--trace-db-path",
            str(trace_db_path),
            "--session-id",
            "agent-review-session",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    run_id = payload["agent_run"]["run_id"]
    trace_store = TraceStore(trace_db_path)
    trace = trace_store.list_by_session_id("agent-review-session")[0]
    envelope = AgentRunStore(trace_db_path).get(run_id)

    assert exit_code == 0
    assert trace_store.list_by_agent_run_id(run_id)[0]["request_id"] == trace["request_id"]
    assert payload["validation"]["passed"] is False
    assert payload["validation"]["guardrail_outcome"] == "needs_review"
    assert payload["validation"]["review_state"] == "needs_review"
    assert payload["validation"]["review_required"] is True
    assert payload["output_summary"]["needs_review"] is True
    assert trace["validation_passed"] is False
    assert trace["guardrail_outcome"] == "needs_review"
    assert envelope is not None
    assert envelope["validation"]["passed"] is False
    assert envelope["guardrail"]["outcome"] == "needs_review"
    assert envelope["range_output"]["output"]["needs_review"] is True
    assert envelope["review"]["state"] == "needs_review"
    assert envelope["review"]["touch_decision"] == "block_downstream_touch"


def test_agents_run_validation_failure_records_rejected_trace(
    capsys,
    monkeypatch,
    tmp_path,
):
    class InvalidProvider:
        name = "invalid-provider"

        def complete(self, request: ProviderRequest) -> ProviderResponse:
            return ProviderResponse(
                text='{"category": "not-a-category"}',
                provider=self.name,
                model=request.model,
                input_tokens=1,
                output_tokens=1,
            )

    trace_db_path = tmp_path / "agent-run-invalid.sqlite3"
    monkeypatch.setattr("blacklight.cli.create_provider", lambda _settings: InvalidProvider())

    exit_code = main(
        [
            "agents",
            "run",
            "ticket_classifier_agent",
            "--subject",
            "Broken output",
            "--body",
            "Synthetic provider returns an invalid schema.",
            "--trace-db-path",
            str(trace_db_path),
            "--session-id",
            "agent-invalid-session",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.err)
    traces = TraceStore(trace_db_path).list_recent()
    envelope = AgentRunStore(trace_db_path).get(payload["agent_run"]["run_id"])

    assert exit_code == 1
    assert captured.out == ""
    assert payload["agent_run"]["run_status"] == "failed"
    assert payload["agent_run"]["session_id"] == "agent-invalid-session"
    assert payload["trace"]["agent_run_id"] == payload["agent_run"]["run_id"]
    assert payload["validation"]["passed"] is False
    assert payload["validation"]["guardrail_outcome"] == "rejected"
    assert payload["validation"]["error_category"] == "validation_error"
    assert payload["validation"]["errors"]
    assert payload["output_summary"] is None
    assert payload["output"] is None
    assert traces[0]["validation_passed"] is False
    assert traces[0]["guardrail_outcome"] == "rejected"
    assert traces[0]["error_category"] == "validation_error"
    assert traces[0]["session_id"] == "agent-invalid-session"
    assert traces[0]["agent_run_id"] == payload["agent_run"]["run_id"]
    assert envelope is not None
    assert envelope["run_status"] == "failed"
    assert envelope["validation"]["passed"] is False
    assert envelope["validation"]["errors"]
    assert envelope["guardrail"]["outcome"] == "rejected"
    assert envelope["range_output"]["output"] is None
    assert envelope["review"]["state"] == "rejected"


def test_prompts_list_command_prints_prompt_metadata(capsys):
    exit_code = main(["prompts", "list"])

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["prompts"][0]["prompt_id"] == "ticket_classifier"
    assert payload["prompts"][0]["version"] == 1
    assert payload["prompts"][0]["comparison_group"] == "support_ticket_classification"
    assert payload["prompts"][0]["output_schema"] == "TicketClassification"


def test_prompts_show_command_prints_template(capsys):
    exit_code = main(["prompts", "show", "ticket_classifier"])

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["prompt_id"] == "ticket_classifier"
    assert payload["display_name"] == "Support Ticket Classifier"
    assert payload["comparison_group"] == "support_ticket_classification"
    assert "Subject: $subject" in payload["template"]


def test_trace_commands_read_trace_records(capsys, tmp_path):
    trace_db_path = tmp_path / "traces.sqlite3"
    main(
        [
            "classify",
            "--subject",
            "Refund",
            "--body",
            "Duplicate charge",
            "--trace-db-path",
            str(trace_db_path),
        ]
    )
    capsys.readouterr()

    list_exit_code = main(["trace", "list", "--trace-db-path", str(trace_db_path)])
    list_payload = json.loads(capsys.readouterr().out)
    request_id = list_payload["traces"][0]["request_id"]

    show_exit_code = main(["trace", "show", request_id, "--trace-db-path", str(trace_db_path)])
    show_payload = json.loads(capsys.readouterr().out)
    traces_show_exit_code = main(["traces", "show", request_id, "--trace-db-path", str(trace_db_path)])
    traces_show_payload = json.loads(capsys.readouterr().out)

    assert list_exit_code == 0
    assert show_exit_code == 0
    assert traces_show_exit_code == 0
    assert list_payload["traces"][0]["prompt_id"] == "ticket_classifier"
    assert show_payload["trace"] == traces_show_payload["trace"]
    assert show_payload["trace"]["request_id"] == request_id
    assert show_payload["trace"]["provider"] == "mock"
    assert show_payload["trace"]["model"] == "mock-ticket-classifier"
    assert show_payload["trace"]["prompt_version"] == 1
    assert show_payload["trace"]["latency_ms"] >= 0
    assert show_payload["trace"]["input_tokens"] > 0
    assert show_payload["trace"]["output_tokens"] > 0
    assert show_payload["trace"]["estimated_cost_usd"] == 0.0
    assert show_payload["trace"]["validation_passed"] is True
    assert show_payload["trace"]["guardrail_outcome"] == "accepted"
    assert show_payload["trace"]["error_category"] is None


def test_trace_show_missing_record_returns_clear_error(capsys, tmp_path):
    trace_db_path = tmp_path / "traces.sqlite3"

    exit_code = main(["trace", "show", "missing-request", "--trace-db-path", str(trace_db_path)])
    captured = capsys.readouterr()
    payload = json.loads(captured.err)

    assert exit_code == 1
    assert captured.out == ""
    assert payload["error"]["category"] == "trace_not_found"
    assert payload["error"]["message"] == "Trace not found: missing-request"
    assert "trace list" in payload["error"]["next_step"]


def test_session_show_prints_chronological_trace_history_and_summary(capsys, tmp_path):
    trace_db_path = tmp_path / "traces.sqlite3"
    store = TraceStore(trace_db_path)
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
        )
    )
    store.insert(
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
            validation_passed=False,
            guardrail_outcome=GuardrailOutcome.needs_review,
            error_category="provider_timeout",
        )
    )

    exit_code = main(
        [
            "session",
            "show",
            "session-a",
            "--trace-db-path",
            str(trace_db_path),
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["session_id"] == "session-a"
    assert [trace["request_id"] for trace in payload["traces"]] == ["request-1", "request-2"]
    assert payload["summary"]["request_count"] == 2
    assert payload["summary"]["total_input_tokens"] == 30
    assert payload["summary"]["total_output_tokens"] == 12
    assert payload["summary"]["total_tokens"] == 42
    assert payload["summary"]["total_estimated_cost_usd"] == 0.00003
    assert payload["summary"]["failure_count"] == 1
    assert payload["summary"]["failure_rate"] == 0.5
    assert payload["summary"]["review_count"] == 1
    assert payload["summary"]["validation_failure_count"] == 1
    assert payload["summary"]["by_provider_model"] == [
        {
            "provider": "mock",
            "model": "mock-ticket-classifier",
            "request_count": 1,
            "total_tokens": 15,
            "total_estimated_cost_usd": 0.0,
            "failure_count": 0,
            "review_count": 0,
            "failure_rate": 0.0,
        },
        {
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "request_count": 1,
            "total_tokens": 27,
            "total_estimated_cost_usd": 0.00003,
            "failure_count": 1,
            "review_count": 1,
            "failure_rate": 1.0,
        },
    ]


def test_session_show_missing_session_returns_clear_error(capsys, tmp_path):
    trace_db_path = tmp_path / "traces.sqlite3"

    exit_code = main(
        [
            "session",
            "show",
            "missing-session",
            "--trace-db-path",
            str(trace_db_path),
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.err)

    assert exit_code == 1
    assert captured.out == ""
    assert payload["error"]["category"] == "session_not_found"
    assert payload["error"]["message"] == "Session not found: missing-session"
    assert "trace list" in payload["error"]["next_step"]


def test_classify_configuration_error_returns_actionable_cli_error(
    capsys,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    exit_code = main(
        [
            "classify",
            "--subject",
            "Refund",
            "--body",
            "Duplicate charge",
            "--trace-db-path",
            str(tmp_path / "traces.sqlite3"),
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.err)

    assert exit_code == 1
    assert captured.out == ""
    assert payload["error"]["category"] == "configuration_error"
    assert "OPENAI_API_KEY" in payload["error"]["message"]
    assert "blacklight health" in payload["error"]["next_step"]


def test_cli_debug_error_mode_reraises_unexpected_errors(monkeypatch):
    def broken_health(_args):
        raise RuntimeError("boom")

    monkeypatch.setattr("blacklight.cli.health", broken_health)
    monkeypatch.setenv("BLACKLIGHT_DEBUG_ERRORS", "1")

    with pytest.raises(RuntimeError, match="boom"):
        main(["health"])

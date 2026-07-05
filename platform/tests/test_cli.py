import json

import pytest

from blacklight.cli import main
from blacklight.models import GuardrailOutcome, TraceRecord
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
    assert payload["provider_timeout_seconds"] == 30.0
    assert payload["provider_max_retries"] == 2
    assert payload["provider_rate_limit_requests"] == 3
    assert payload["provider_rate_limit_window_seconds"] == 10.0


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

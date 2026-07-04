import json

from llm_platform_starter.cli import main
from llm_platform_starter.observability.evaluations import EvalMetricStore


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


def test_prompts_show_command_prints_template(capsys):
    exit_code = main(["prompts", "show", "ticket_classifier"])

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["prompt_id"] == "ticket_classifier"
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

    assert exit_code == 1
    assert captured.out == ""
    assert "Trace not found: missing-request" in captured.err

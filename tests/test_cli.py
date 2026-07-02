import json

from llm_platform_starter.cli import main


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


def test_eval_command_prints_summary(capsys):
    exit_code = main(["eval"])

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["accuracy"] == 1.0
    assert payload["cases"]


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


def test_health_command_prints_runtime_config(capsys):
    exit_code = main(["health"])

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["provider"] == "mock"
    assert payload["model"] == "mock-ticket-classifier"
    assert payload["openai_configured"] is False
    assert payload["custom_provider_configured"] is False


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

    assert list_exit_code == 0
    assert show_exit_code == 0
    assert list_payload["traces"][0]["prompt_id"] == "ticket_classifier"
    assert show_payload["trace"]["request_id"] == request_id

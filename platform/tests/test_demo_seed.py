from blacklight.demo_seed import (
    DEMO_SEED_EVAL_RUN_ID,
    DEMO_SEED_SESSION_ID,
    seed_demo_data,
)
from blacklight.observability.evaluations import EvalMetricStore
from blacklight.observability.storage import TraceStore


def test_seed_demo_data_creates_linked_mock_records(tmp_path):
    db_path = tmp_path / "seed.sqlite3"

    payload = seed_demo_data(str(db_path))
    trace_store = TraceStore(db_path)
    eval_store = EvalMetricStore(db_path)
    session_traces = trace_store.list_by_session_id(DEMO_SEED_SESSION_ID, limit=20)
    eval_run = eval_store.get_run(DEMO_SEED_EVAL_RUN_ID)
    reviewable = trace_store.list_reviewable()

    assert payload["seed"] == "mock_mode_demo_data"
    assert payload["session_id"] == DEMO_SEED_SESSION_ID
    assert len(payload["sample_inputs"]) == 2
    assert [run["guardrail_outcome"] for run in payload["runs"]] == [
        "accepted",
        "needs_review",
    ]
    assert payload["eval_run"]["eval_run_id"] == DEMO_SEED_EVAL_RUN_ID
    assert payload["eval_run"]["case_count"] == 3
    assert len(payload["eval_run"]["trace_request_ids"]) == 3
    assert {prompt["version"] for prompt in payload["prompt_versions"]} == {1, 2}
    assert "session show seed-demo" in payload["inspect_commands"]["session"]
    assert len(session_traces) == 5
    assert {trace["request_id"] for trace in session_traces}.issuperset(
        {
            "seed-demo:billing-success",
            "seed-demo:account-needs-review",
            "seed-demo-eval:billing_refund",
        }
    )
    assert eval_run is not None
    assert eval_run["session_id"] == DEMO_SEED_SESSION_ID
    assert eval_run["cases"][0]["trace_request_id"] in payload["eval_run"]["trace_request_ids"]
    assert any(trace["request_id"] == "seed-demo:account-needs-review" for trace in reviewable)


def test_seed_demo_data_is_stable_when_rerun(tmp_path):
    db_path = tmp_path / "seed.sqlite3"

    seed_demo_data(str(db_path))
    seed_demo_data(str(db_path))

    trace_store = TraceStore(db_path)
    eval_store = EvalMetricStore(db_path)

    assert trace_store.metrics()["request_count"] == 5
    assert len(trace_store.list_by_session_id(DEMO_SEED_SESSION_ID, limit=20)) == 5
    assert len(eval_store.list_cases(DEMO_SEED_EVAL_RUN_ID)) == 3

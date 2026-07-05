from blacklight.evals.runner import (
    compare_ticket_classification_prompt_versions,
    run_ticket_classification_eval,
)
from blacklight.models import ProviderRequest, ProviderResponse
from blacklight.observability.evaluations import EvalMetricStore
from blacklight.observability.storage import TraceStore
from blacklight.providers.mock import MockProvider


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        current = self.now
        self.now += 0.001
        return current


class FailsOnceMockProvider(MockProvider):
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary provider failure")
        return super().complete(request)


def test_ticket_classification_eval_passes_with_mock_provider():
    report = run_ticket_classification_eval(monotonic=FakeClock().monotonic)
    summary = report["summary"]

    assert set(report) == {
        "eval_run_id",
        "session_id",
        "fixture_name",
        "prompt_id",
        "prompt_version",
        "provider",
        "model",
        "summary",
        "cases",
    }
    assert report["session_id"] == "eval"
    assert report["fixture_name"] == "ticket_classification.jsonl"
    assert summary["case_count"] == 3
    assert summary["accuracy"] == 1.0
    assert summary["schema_validity_rate"] == 1.0
    assert summary["needs_review_rate"] == 0.3333
    assert summary["average_latency_ms"] == 1.0
    assert summary["latency_p50_ms"] == 1.0
    assert summary["latency_p95_ms"] == 1.0
    assert summary["total_input_tokens"] > 0
    assert summary["total_output_tokens"] > 0
    assert summary["total_tokens"] == summary["total_input_tokens"] + summary["total_output_tokens"]
    assert summary["tokens_per_case"] > 0
    assert summary["total_estimated_cost_usd"] == 0.0
    assert summary["cost_per_successful_case"] == 0.0
    assert summary["total_retries"] == 0
    assert summary["average_retries_per_case"] == 0.0
    assert summary["error_rate"] == 0.0
    assert summary["failure_categories"] == {}
    assert summary["confidence_average"] > 0
    assert summary["low_confidence_count"] == 0
    assert summary["schema_error_examples"] == []
    assert summary["category_breakdown"] == {
        "account": {"case_count": 1, "accuracy": 1.0},
        "billing": {"case_count": 1, "accuracy": 1.0},
        "technical": {"case_count": 1, "accuracy": 1.0},
    }
    assert all(case["passed"] for case in report["cases"])


def test_ticket_classification_eval_reports_case_diagnostics():
    report = run_ticket_classification_eval(monotonic=FakeClock().monotonic)
    case = report["cases"][0]

    assert set(case) == {
        "id",
        "trace_request_id",
        "expected_category",
        "actual_category",
        "passed",
        "schema_valid",
        "needs_review",
        "confidence",
        "latency_ms",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "estimated_cost_usd",
        "retry_count",
        "error_category",
        "validation_errors",
    }
    assert case["trace_request_id"].endswith(":billing_refund")
    assert case["expected_category"] == "billing"
    assert case["actual_category"] == "billing"
    assert case["schema_valid"] is True
    assert case["needs_review"] is False
    assert case["latency_ms"] == 1.0
    assert case["total_tokens"] == case["input_tokens"] + case["output_tokens"]
    assert case["retry_count"] == 0
    assert case["error_category"] is None
    assert case["validation_errors"] == []


def test_ticket_classification_eval_accepts_prompt_version():
    report = run_ticket_classification_eval(
        prompt_version=2,
        monotonic=FakeClock().monotonic,
    )

    assert report["prompt_version"] == 2
    assert report["summary"]["accuracy"] == 1.0
    assert all(case["schema_valid"] for case in report["cases"])


def test_prompt_version_comparison_report_is_deterministic():
    report = compare_ticket_classification_prompt_versions(
        baseline_version=1,
        candidate_version=2,
        session_id="compare-test",
        monotonic=FakeClock().monotonic,
    )

    assert set(report) == {
        "prompt_id",
        "comparison_group",
        "output_schema",
        "fixture_name",
        "baseline",
        "candidate",
        "summary_deltas",
        "case_changes",
    }
    assert report["comparison_group"] == "support_ticket_classification"
    assert report["output_schema"] == "TicketClassification"
    assert report["baseline"]["prompt_version"] == 1
    assert report["candidate"]["prompt_version"] == 2
    assert report["summary_deltas"]["accuracy"] == {
        "baseline": 1.0,
        "candidate": 1.0,
        "delta": 0.0,
    }
    assert report["summary_deltas"]["schema_validity_rate"]["delta"] == 0.0
    assert report["summary_deltas"]["needs_review_rate"]["delta"] == 0.0
    assert report["summary_deltas"]["tokens_per_case"]["delta"] > 0
    assert len(report["case_changes"]) == 3
    assert all(change["changed"] is False for change in report["case_changes"])
    assert all(change["deltas"]["total_tokens"] > 0 for change in report["case_changes"])


def test_ticket_classification_eval_reports_retries():
    provider = FailsOnceMockProvider()

    report = run_ticket_classification_eval(
        provider=provider,
        monotonic=FakeClock().monotonic,
    )

    assert provider.calls == 4
    assert report["summary"]["total_retries"] == 1
    assert report["summary"]["average_retries_per_case"] == 0.3333
    assert report["cases"][0]["retry_count"] == 1
    assert report["cases"][1]["retry_count"] == 0


def test_ticket_classification_eval_persists_metrics_by_session(tmp_path):
    db_path = tmp_path / "metrics.sqlite3"
    store = EvalMetricStore(db_path)
    trace_store = TraceStore(db_path)

    report = run_ticket_classification_eval(
        eval_run_id="eval-run-1",
        session_id="session-a",
        eval_store=store,
        trace_store=trace_store,
        monotonic=FakeClock().monotonic,
    )

    runs = store.list_runs()
    stored = store.get_run("eval-run-1")
    stored_cases = store.list_cases("eval-run-1")
    trace = trace_store.get_by_request_id("eval-run-1:billing_refund")

    assert runs[0]["eval_run_id"] == "eval-run-1"
    assert runs[0]["session_id"] == "session-a"
    assert runs[0]["accuracy"] == 1.0
    assert stored is not None
    assert stored["session_id"] == "session-a"
    assert stored["fixture_name"] == "ticket_classification.jsonl"
    assert stored["prompt_id"] == "ticket_classifier"
    assert stored["provider"] == "mock"
    assert stored["model"] == "mock-ticket-classifier"
    assert stored["summary"] == report["summary"]
    assert stored["cases"][0]["trace_request_id"] == "eval-run-1:billing_refund"
    assert stored_cases == stored["cases"]
    assert trace is not None
    assert trace["request_id"] == stored["cases"][0]["trace_request_id"]
    assert trace["session_id"] == "session-a"
    assert trace["eval_run_id"] == "eval-run-1"


def test_ticket_classification_eval_upsert_replaces_cases_without_duplicates(tmp_path):
    db_path = tmp_path / "metrics.sqlite3"
    store = EvalMetricStore(db_path)
    trace_store = TraceStore(db_path)

    run_ticket_classification_eval(
        eval_run_id="eval-run-1",
        session_id="session-a",
        eval_store=store,
        trace_store=trace_store,
        monotonic=FakeClock().monotonic,
    )
    run_ticket_classification_eval(
        eval_run_id="eval-run-1",
        session_id="session-a",
        eval_store=store,
        trace_store=trace_store,
        monotonic=FakeClock().monotonic,
    )

    stored = store.get_run("eval-run-1")
    trace_metrics = trace_store.metrics()

    assert stored is not None
    assert len(stored["cases"]) == 3
    assert trace_metrics["request_count"] == 3
    assert {case["id"] for case in stored["cases"]} == {
        "account_access",
        "billing_refund",
        "technical_api",
    }

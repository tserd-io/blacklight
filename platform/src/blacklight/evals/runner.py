from __future__ import annotations

import json
import time
import uuid
from collections import Counter, defaultdict
from collections.abc import Callable
from importlib import resources
from statistics import median

from blacklight.evals.metrics import accuracy
from blacklight.guardrails.validation import validate_ticket_output
from blacklight.models import (
    GuardrailOutcome,
    ProviderRequest,
    TraceRecord,
    ticket_classification_output_schema,
)
from blacklight.observability.cost import estimate_cost
from blacklight.observability.evaluations import EvalMetricStore
from blacklight.observability.storage import TraceStore
from blacklight.prompts.registry import PromptRegistry, PromptTemplate
from blacklight.providers.base import LLMProvider
from blacklight.providers.mock import MockProvider
from blacklight.providers.reliability import ProviderCallError, complete_with_retries


def load_fixture(name: str = "ticket_classification.jsonl") -> list[dict]:
    raw = resources.files("blacklight.evals.fixtures").joinpath(name).read_text(
        encoding="utf-8"
    )
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def run_ticket_classification_eval(
    *,
    provider: LLMProvider | None = None,
    model: str = "mock-ticket-classifier",
    session_id: str = "eval",
    eval_run_id: str | None = None,
    prompt_id: str = "ticket_classifier",
    prompt_version: int | None = None,
    fixture_name: str | None = None,
    eval_store: EvalMetricStore | None = None,
    trace_store: TraceStore | None = None,
    timeout_seconds: float = 30.0,
    max_retries: int = 2,
    monotonic: Callable[[], float] = time.perf_counter,
) -> dict:
    provider = provider or MockProvider()
    eval_run_id = eval_run_id or str(uuid.uuid4())
    prompt_template = PromptRegistry().get(prompt_id, version=prompt_version)
    fixture_name = fixture_name or prompt_template.eval_fixture or "ticket_classification.jsonl"
    rows = load_fixture(fixture_name)
    checks: list[bool] = []
    cases = []
    for row in rows:
        prompt = prompt_template.render(subject=row["subject"], body=row["body"])
        trace_request_id = f"{eval_run_id}:{row['id']}"
        started = monotonic()
        validation_passed = False
        guardrail_outcome = GuardrailOutcome.rejected
        trace_provider = provider.name
        trace_model = model
        case = {
            "id": row["id"],
            "trace_request_id": trace_request_id,
            "expected_category": row["expected_category"],
            "actual_category": None,
            "passed": False,
            "schema_valid": False,
            "needs_review": False,
            "confidence": None,
            "latency_ms": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "estimated_cost_usd": 0.0,
            "retry_count": 0,
            "error_category": None,
            "validation_errors": [],
        }
        try:
            response = complete_with_retries(
                provider,
                ProviderRequest(
                    prompt=prompt,
                    model=model,
                    output_format="json_object",
                    output_schema_name="ticket_classification",
                    output_schema=ticket_classification_output_schema(),
                    metadata={
                        "request_id": trace_request_id,
                        "session_id": session_id,
                        "prompt_id": prompt_template.prompt_id,
                    },
                ),
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
            )
            parsed, validation = validate_ticket_output(
                response.text,
                source_text=f"{row['subject']}\n{row['body']}",
            )
            validation_passed = validation.passed
            guardrail_outcome = validation.outcome
            trace_provider = response.provider
            trace_model = response.model
            schema_valid = parsed is not None and not validation.errors
            actual_category = parsed.category.value if parsed else None
            passed = actual_category == row["expected_category"]
            input_tokens = response.input_tokens
            output_tokens = response.output_tokens
            retry_count = int(response.metadata.get("retry_count", 0))
            case.update(
                {
                    "actual_category": actual_category,
                    "passed": passed,
                    "schema_valid": schema_valid,
                    "needs_review": bool(parsed.needs_review) if parsed else False,
                    "confidence": parsed.confidence if parsed else None,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                    "estimated_cost_usd": estimate_cost(model, input_tokens, output_tokens),
                    "retry_count": retry_count,
                    "error_category": None if schema_valid else "validation_error",
                    "validation_errors": validation.errors,
                }
            )
        except ProviderCallError as exc:
            passed = False
            case.update(
                {
                    "retry_count": max(exc.attempts - 1, 0),
                    "error_category": exc.category,
                }
            )
        finally:
            case["latency_ms"] = round((monotonic() - started) * 1000, 2)
            if trace_store:
                trace_store.insert(
                    TraceRecord(
                        request_id=trace_request_id,
                        session_id=session_id,
                        eval_run_id=eval_run_id,
                        prompt_id=prompt_template.prompt_id,
                        prompt_version=prompt_template.version,
                        provider=trace_provider,
                        model=trace_model,
                        latency_ms=case["latency_ms"],
                        input_tokens=case["input_tokens"],
                        output_tokens=case["output_tokens"],
                        estimated_cost_usd=case["estimated_cost_usd"],
                        validation_passed=validation_passed,
                        guardrail_outcome=guardrail_outcome,
                        error_category=case["error_category"],
                    )
                )

        checks.append(passed)
        cases.append(case)

    report = {
        "eval_run_id": eval_run_id,
        "session_id": session_id,
        "fixture_name": fixture_name,
        "prompt_id": prompt_template.prompt_id,
        "prompt_version": prompt_template.version,
        "provider": provider.name,
        "model": model,
        "summary": _build_summary(cases, checks),
        "cases": cases,
    }
    if eval_store:
        eval_store.insert_report(report)
    return report


def compare_ticket_classification_prompt_versions(
    *,
    baseline_version: int,
    candidate_version: int,
    provider_factory: Callable[[], LLMProvider] = MockProvider,
    model: str = "mock-ticket-classifier",
    session_id: str = "eval-compare",
    prompt_id: str = "ticket_classifier",
    fixture_name: str | None = None,
    timeout_seconds: float = 30.0,
    max_retries: int = 2,
    monotonic: Callable[[], float] | None = None,
) -> dict:
    monotonic = monotonic or _deterministic_monotonic()
    registry = PromptRegistry()
    baseline_prompt = registry.get(prompt_id, version=baseline_version)
    candidate_prompt = registry.get(prompt_id, version=candidate_version)
    _validate_comparable_prompts(baseline_prompt, candidate_prompt)

    baseline_report = run_ticket_classification_eval(
        provider=provider_factory(),
        model=model,
        session_id=session_id,
        eval_run_id=f"{session_id}:prompt-{baseline_version}",
        prompt_id=prompt_id,
        prompt_version=baseline_version,
        fixture_name=fixture_name,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        monotonic=monotonic,
    )
    candidate_report = run_ticket_classification_eval(
        provider=provider_factory(),
        model=model,
        session_id=session_id,
        eval_run_id=f"{session_id}:prompt-{candidate_version}",
        prompt_id=prompt_id,
        prompt_version=candidate_version,
        fixture_name=fixture_name,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        monotonic=monotonic,
    )

    return {
        "prompt_id": prompt_id,
        "comparison_group": baseline_prompt.comparison_group,
        "output_schema": baseline_prompt.output_schema,
        "fixture_name": baseline_report["fixture_name"],
        "baseline": _prompt_report_summary(baseline_report),
        "candidate": _prompt_report_summary(candidate_report),
        "summary_deltas": _summary_deltas(
            baseline_report["summary"],
            candidate_report["summary"],
        ),
        "case_changes": _case_changes(
            baseline_report["cases"],
            candidate_report["cases"],
        ),
    }


def _validate_comparable_prompts(
    baseline_prompt: PromptTemplate,
    candidate_prompt: PromptTemplate,
) -> None:
    required_matches = {
        "comparison_group": (
            baseline_prompt.comparison_group,
            candidate_prompt.comparison_group,
        ),
        "output_schema": (
            baseline_prompt.output_schema,
            candidate_prompt.output_schema,
        ),
        "eval_fixture": (
            baseline_prompt.eval_fixture,
            candidate_prompt.eval_fixture,
        ),
    }
    mismatches = [
        field
        for field, (baseline, candidate) in required_matches.items()
        if baseline != candidate
    ]
    if mismatches:
        raise ValueError(
            "Prompt versions are not comparable because these fields differ: "
            + ", ".join(mismatches)
        )


def _prompt_report_summary(report: dict) -> dict:
    return {
        "eval_run_id": report["eval_run_id"],
        "prompt_version": report["prompt_version"],
        "provider": report["provider"],
        "model": report["model"],
        "summary": report["summary"],
    }


def _summary_deltas(baseline_summary: dict, candidate_summary: dict) -> dict:
    metrics = [
        "accuracy",
        "schema_validity_rate",
        "needs_review_rate",
        "average_latency_ms",
        "latency_p50_ms",
        "latency_p95_ms",
        "total_estimated_cost_usd",
        "tokens_per_case",
    ]
    return {
        metric: {
            "baseline": baseline_summary[metric],
            "candidate": candidate_summary[metric],
            "delta": round(candidate_summary[metric] - baseline_summary[metric], 8),
        }
        for metric in metrics
    }


def _case_changes(baseline_cases: list[dict], candidate_cases: list[dict]) -> list[dict]:
    candidate_by_id = {case["id"]: case for case in candidate_cases}
    changes = []
    for baseline_case in baseline_cases:
        candidate_case = candidate_by_id[baseline_case["id"]]
        changed_fields = [
            field
            for field in [
                "actual_category",
                "passed",
                "schema_valid",
                "needs_review",
                "confidence",
                "error_category",
            ]
            if baseline_case[field] != candidate_case[field]
        ]
        changes.append(
            {
                "id": baseline_case["id"],
                "expected_category": baseline_case["expected_category"],
                "changed": bool(changed_fields),
                "changed_fields": changed_fields,
                "baseline": _case_comparison_slice(baseline_case),
                "candidate": _case_comparison_slice(candidate_case),
                "deltas": {
                    "latency_ms": round(
                        candidate_case["latency_ms"] - baseline_case["latency_ms"],
                        4,
                    ),
                    "total_tokens": candidate_case["total_tokens"] - baseline_case["total_tokens"],
                    "estimated_cost_usd": round(
                        candidate_case["estimated_cost_usd"]
                        - baseline_case["estimated_cost_usd"],
                        8,
                    ),
                },
            }
        )
    return changes


def _case_comparison_slice(case: dict) -> dict:
    return {
        "actual_category": case["actual_category"],
        "passed": case["passed"],
        "schema_valid": case["schema_valid"],
        "needs_review": case["needs_review"],
        "confidence": case["confidence"],
        "latency_ms": case["latency_ms"],
        "total_tokens": case["total_tokens"],
        "estimated_cost_usd": case["estimated_cost_usd"],
        "error_category": case["error_category"],
    }


def _deterministic_monotonic(step_seconds: float = 0.001) -> Callable[[], float]:
    current = 0.0

    def monotonic() -> float:
        nonlocal current
        value = current
        current += step_seconds
        return value

    return monotonic


def _build_summary(cases: list[dict], checks: list[bool]) -> dict:
    case_count = len(cases)
    successful_cases = [case for case in cases if case["passed"]]
    latencies = [case["latency_ms"] for case in cases]
    total_input_tokens = sum(case["input_tokens"] for case in cases)
    total_output_tokens = sum(case["output_tokens"] for case in cases)
    total_tokens = total_input_tokens + total_output_tokens
    total_cost = round(sum(case["estimated_cost_usd"] for case in cases), 8)
    total_retries = sum(case["retry_count"] for case in cases)
    schema_checks = [case["schema_valid"] for case in cases]
    review_checks = [case["needs_review"] for case in cases]
    errors = Counter(
        case["error_category"] for case in cases if case["error_category"] is not None
    )
    confidences = [
        case["confidence"] for case in cases if isinstance(case["confidence"], int | float)
    ]

    return {
        "case_count": case_count,
        "accuracy": accuracy(checks),
        "schema_validity_rate": accuracy(schema_checks),
        "needs_review_rate": accuracy(review_checks),
        "average_latency_ms": _average(latencies),
        "latency_p50_ms": _percentile(latencies, 50),
        "latency_p95_ms": _percentile(latencies, 95),
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_tokens": total_tokens,
        "tokens_per_case": _safe_divide(total_tokens, case_count),
        "total_estimated_cost_usd": total_cost,
        "cost_per_successful_case": _safe_divide(total_cost, len(successful_cases)),
        "total_retries": total_retries,
        "average_retries_per_case": _safe_divide(total_retries, case_count),
        "error_rate": _safe_divide(sum(1 for case in cases if case["error_category"]), case_count),
        "failure_categories": dict(sorted(errors.items())),
        "category_breakdown": _category_breakdown(cases),
        "confidence_average": _average(confidences),
        "low_confidence_count": sum(
            1 for confidence in confidences if confidence < 0.75
        ),
        "schema_error_examples": [
            {"id": case["id"], "errors": case["validation_errors"]}
            for case in cases
            if case["validation_errors"]
        ],
    }


def _category_breakdown(cases: list[dict]) -> dict:
    by_category: dict[str, list[bool]] = defaultdict(list)
    for case in cases:
        by_category[case["expected_category"]].append(case["passed"])
    return {
        category: {
            "case_count": len(results),
            "accuracy": accuracy(results),
        }
        for category, results in sorted(by_category.items())
    }


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    if percentile == 50:
        return round(median(values), 4)
    sorted_values = sorted(values)
    index = round((len(sorted_values) - 1) * percentile / 100)
    return round(sorted_values[index], 4)


def _safe_divide(numerator: float, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def main() -> None:
    print(json.dumps(run_ticket_classification_eval(), indent=2))


if __name__ == "__main__":
    main()

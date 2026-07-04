from __future__ import annotations

import json
import time
import uuid
from collections import Counter, defaultdict
from collections.abc import Callable
from importlib import resources
from statistics import median

from llm_platform_starter.evals.metrics import accuracy
from llm_platform_starter.guardrails.validation import validate_ticket_output
from llm_platform_starter.models import GuardrailOutcome, ProviderRequest, TraceRecord
from llm_platform_starter.observability.cost import estimate_cost
from llm_platform_starter.observability.evaluations import EvalMetricStore
from llm_platform_starter.observability.storage import TraceStore
from llm_platform_starter.prompts.registry import PromptRegistry
from llm_platform_starter.providers.base import LLMProvider
from llm_platform_starter.providers.mock import MockProvider
from llm_platform_starter.providers.reliability import ProviderCallError, complete_with_retries


def load_fixture(name: str = "ticket_classification.jsonl") -> list[dict]:
    raw = resources.files("llm_platform_starter.evals.fixtures").joinpath(name).read_text(
        encoding="utf-8"
    )
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def run_ticket_classification_eval(
    *,
    provider: LLMProvider | None = None,
    model: str = "mock-ticket-classifier",
    session_id: str = "eval",
    eval_run_id: str | None = None,
    fixture_name: str = "ticket_classification.jsonl",
    eval_store: EvalMetricStore | None = None,
    trace_store: TraceStore | None = None,
    timeout_seconds: float = 30.0,
    max_retries: int = 2,
    monotonic: Callable[[], float] = time.perf_counter,
) -> dict:
    provider = provider or MockProvider()
    eval_run_id = eval_run_id or str(uuid.uuid4())
    prompt_template = PromptRegistry().get("ticket_classifier")
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

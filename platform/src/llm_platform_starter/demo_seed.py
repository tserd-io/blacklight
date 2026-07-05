from __future__ import annotations

from typing import Any

from collections.abc import Callable

from llm_platform_starter.evals.runner import run_ticket_classification_eval
from llm_platform_starter.guardrails.validation import validate_ticket_output
from llm_platform_starter.models import ProviderRequest, TraceRecord
from llm_platform_starter.observability.cost import estimate_cost
from llm_platform_starter.observability.evaluations import EvalMetricStore
from llm_platform_starter.observability.storage import TraceStore
from llm_platform_starter.prompts.registry import PromptRegistry, PromptTemplate
from llm_platform_starter.providers.mock import MockProvider

DEMO_SEED_SESSION_ID = "seed-demo"
DEMO_SEED_EVAL_RUN_ID = "seed-demo-eval"
DEMO_SEED_MODEL = "mock-ticket-classifier"

DEMO_TICKET_INPUTS = [
    {
        "id": "billing_success",
        "trace_request_id": "seed-demo:billing-success",
        "subject": "Refund request",
        "body": "Customer asks for a refund after duplicate billing.",
        "expected_outcome": "accepted",
    },
    {
        "id": "account_needs_review",
        "trace_request_id": "seed-demo:account-needs-review",
        "subject": "Account access review",
        "body": "Customer reports possible fraud and included a credit card reference.",
        "expected_outcome": "needs_review",
    },
]


def seed_demo_data(db_path: str) -> dict[str, Any]:
    trace_store = TraceStore(db_path)
    eval_store = EvalMetricStore(db_path)
    prompt_registry = PromptRegistry()
    prompt = prompt_registry.get("ticket_classifier")
    provider = MockProvider()

    runs = [
        _seed_ticket_run(
            sample=sample,
            prompt=prompt,
            provider=provider,
            trace_store=trace_store,
        )
        for sample in DEMO_TICKET_INPUTS
    ]
    eval_report = run_ticket_classification_eval(
        provider=MockProvider(),
        model=DEMO_SEED_MODEL,
        session_id=DEMO_SEED_SESSION_ID,
        eval_run_id=DEMO_SEED_EVAL_RUN_ID,
        eval_store=eval_store,
        trace_store=trace_store,
        monotonic=_deterministic_monotonic(),
    )
    prompt_versions = [
        _prompt_metadata(prompt_registry.get("ticket_classifier", version=version))
        for version in [1, 2]
    ]

    return {
        "seed": "mock_mode_demo_data",
        "trace_db_path": db_path,
        "session_id": DEMO_SEED_SESSION_ID,
        "sample_inputs": DEMO_TICKET_INPUTS,
        "runs": runs,
        "eval_run": {
            "eval_run_id": eval_report["eval_run_id"],
            "session_id": eval_report["session_id"],
            "case_count": eval_report["summary"]["case_count"],
            "trace_request_ids": [case["trace_request_id"] for case in eval_report["cases"]],
        },
        "prompt_versions": prompt_versions,
        "inspect_commands": {
            "session": f"llm-platform session show {DEMO_SEED_SESSION_ID} --trace-db-path {db_path}",
            "eval": f"llm-platform eval show {DEMO_SEED_EVAL_RUN_ID} --trace-db-path {db_path}",
            "traces": f"llm-platform trace list --trace-db-path {db_path} --limit 10",
        },
    }


def _seed_ticket_run(
    *,
    sample: dict[str, str],
    prompt: PromptTemplate,
    provider: MockProvider,
    trace_store: TraceStore,
) -> dict[str, Any]:
    rendered_prompt = prompt.render(subject=sample["subject"], body=sample["body"])
    response = provider.complete(
        ProviderRequest(
            prompt=rendered_prompt,
            model=DEMO_SEED_MODEL,
            metadata={
                "request_id": sample["trace_request_id"],
                "session_id": DEMO_SEED_SESSION_ID,
                "prompt_id": prompt.prompt_id,
            },
        )
    )
    parsed, validation = validate_ticket_output(
        response.text,
        source_text=f"{sample['subject']}\n{sample['body']}",
    )
    trace_store.insert(
        TraceRecord(
            request_id=sample["trace_request_id"],
            session_id=DEMO_SEED_SESSION_ID,
            prompt_id=prompt.prompt_id,
            prompt_version=prompt.version,
            provider=response.provider,
            model=response.model,
            latency_ms=1.0,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            estimated_cost_usd=estimate_cost(
                response.model,
                response.input_tokens,
                response.output_tokens,
            ),
            validation_passed=validation.passed,
            guardrail_outcome=validation.outcome,
            error_category=None,
        )
    )
    return {
        "id": sample["id"],
        "trace_request_id": sample["trace_request_id"],
        "session_id": DEMO_SEED_SESSION_ID,
        "guardrail_outcome": validation.outcome.value,
        "validation_passed": validation.passed,
        "category": parsed.category.value if parsed else None,
        "needs_review": parsed.needs_review if parsed else False,
        "links": {
            "trace": sample["trace_request_id"],
            "session": DEMO_SEED_SESSION_ID,
        },
    }


def _prompt_metadata(prompt: PromptTemplate) -> dict[str, Any]:
    return {
        "prompt_id": prompt.prompt_id,
        "version": prompt.version,
        "display_name": prompt.display_name,
        "active": prompt.active,
        "domain": prompt.domain,
        "task_type": prompt.task_type,
        "output_schema": prompt.output_schema,
        "eval_fixture": prompt.eval_fixture,
        "comparison_group": prompt.comparison_group,
        "tags": prompt.tags,
        "notes": prompt.notes,
    }


def _deterministic_monotonic(step_seconds: float = 0.001) -> Callable[[], float]:
    current = 0.0

    def monotonic() -> float:
        nonlocal current
        value = current
        current += step_seconds
        return value

    return monotonic

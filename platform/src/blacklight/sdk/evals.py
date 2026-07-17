from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from blacklight.eval_evidence import build_eval_evidence
from blacklight.evals.runner import (
    compare_ticket_classification_prompt_versions,
    run_ticket_classification_eval,
)
from blacklight.observability.evaluations import EvalMetricStore
from blacklight.observability.storage import TraceStore
from blacklight.providers.base import LLMProvider
from blacklight.providers.mock import MockProvider
from blacklight.sdk.errors import SDKNotFoundError
from blacklight.settings import Settings

ProviderFactory = Callable[[], LLMProvider]


class EvalRunResult(BaseModel):
    report: dict[str, Any]


class EvalListResult(BaseModel):
    eval_runs: list[dict[str, Any]] = Field(default_factory=list)


class EvalDetail(BaseModel):
    eval_run: dict[str, Any]
    traces: list[dict[str, Any]] = Field(default_factory=list)


class EvalComparisonResult(BaseModel):
    comparison: dict[str, Any]


class EvalClient:
    def __init__(self, *, provider: LLMProvider, settings: Settings, provider_source: str) -> None:
        self._provider = provider
        self._settings = settings
        self._provider_source = provider_source

    def run(
        self,
        *,
        session_id: str = "eval",
        eval_run_id: str | None = None,
        prompt_version: int | None = None,
        fixture_name: str | None = None,
    ) -> EvalRunResult:
        db_path = self._settings.trace_db_path
        report = run_ticket_classification_eval(
            provider=self._provider,
            model=self._settings.model,
            session_id=session_id,
            eval_run_id=eval_run_id,
            prompt_version=prompt_version,
            fixture_name=fixture_name,
            eval_store=EvalMetricStore(db_path),
            trace_store=TraceStore(db_path),
            timeout_seconds=self._settings.provider_timeout_seconds,
            max_retries=self._settings.provider_max_retries,
        )
        return EvalRunResult(report=report)

    def list(self, *, limit: int = 10) -> EvalListResult:
        return EvalListResult(
            eval_runs=EvalMetricStore(self._settings.trace_db_path).list_runs(limit=limit)
        )

    def show(self, eval_run_id: str) -> EvalDetail:
        db_path = self._settings.trace_db_path
        eval_store = EvalMetricStore(db_path)
        run = eval_store.get_run(eval_run_id)
        if run is None:
            raise SDKNotFoundError(f"Eval run not found: {eval_run_id}")
        traces = [
            {
                **trace,
                "eval_evidence": build_eval_evidence(
                    trace,
                    trace_db_path=db_path,
                ),
            }
            for trace in TraceStore(db_path).list_by_eval_run_id(eval_run_id)
        ]
        return EvalDetail(eval_run=run, traces=traces)

    def compare(
        self,
        *,
        baseline_version: int,
        candidate_version: int,
        session_id: str = "eval-compare",
        prompt_id: str = "ticket_classifier",
        fixture_name: str | None = None,
        provider_factory: ProviderFactory | None = None,
    ) -> EvalComparisonResult:
        resolved_provider_factory = provider_factory or self._default_comparison_provider_factory()

        return EvalComparisonResult(
            comparison=compare_ticket_classification_prompt_versions(
                baseline_version=baseline_version,
                candidate_version=candidate_version,
                provider_factory=resolved_provider_factory,
                model=self._settings.model,
                session_id=session_id,
                prompt_id=prompt_id,
                fixture_name=fixture_name,
                timeout_seconds=self._settings.provider_timeout_seconds,
                max_retries=self._settings.provider_max_retries,
            )
        )

    def _default_comparison_provider_factory(self) -> ProviderFactory:
        if self._provider_source == "mock":
            return MockProvider
        raise ValueError(
            "client.evals.compare() requires provider_factory for injected providers "
            "so baseline and candidate evals receive isolated provider instances."
        )

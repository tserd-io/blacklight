from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from blacklight.eval_evidence import build_eval_evidence
from blacklight.observability.storage import TraceStore
from blacklight.sdk.errors import SDKNotFoundError
from blacklight.settings import Settings


class TraceListResult(BaseModel):
    traces: list[dict[str, Any]] = Field(default_factory=list)


class TraceDetail(BaseModel):
    trace: dict[str, Any]
    eval_evidence: dict[str, Any]


class TraceClient:
    def __init__(self, *, settings: Settings) -> None:
        self._settings = settings

    def list(self, *, limit: int = 10) -> TraceListResult:
        return TraceListResult(
            traces=TraceStore(self._settings.trace_db_path).list_recent(limit=limit)
        )

    def show(self, trace_id: str) -> TraceDetail:
        trace = TraceStore(self._settings.trace_db_path).get_by_request_id(trace_id)
        if trace is None:
            raise SDKNotFoundError(f"Trace not found: {trace_id}")
        return TraceDetail(
            trace=trace,
            eval_evidence=build_eval_evidence(
                trace,
                trace_db_path=self._settings.trace_db_path,
            ),
        )
